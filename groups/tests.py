from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase, RequestFactory
from rest_framework.test import APIClient

from .models import Group, GroupMembership, GroupInvitation

User = get_user_model()


def user(name, **kwargs):
    return User.objects.create_user(email=f'{name}@example.com', username=name, full_name=name, password='A-long-test-password-345', email_verified=True, **kwargs)


class GroupsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = user('owner')
        cls.member = user('member')
        cls.outsider = user('outsider')
        cls.group = Group.objects.create(name='Trip', created_by=cls.owner)
        cls.admin_member = GroupMembership.objects.create(group=cls.group, user=cls.owner, role='admin')
        cls.membership = GroupMembership.objects.create(group=cls.group, user=cls.member, role='member')

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.base = f'/api/v1/groups/{self.group.pk}/'

    def invite(self, target=None):
        return self.client.post(self.base + 'invitations/', {'username': (target or self.outsider).username}, format='json')

    def action(self, invitation, action):
        return self.client.post(f'/api/v1/invitations/{invitation}/{action}/', {}, format='json')

    def test_create_group(self):
        response = self.client.post('/api/v1/groups/', {'name': '  New Trip  '}, format='json')
        self.assertEqual(response.status_code, 201)
        data = response.data['group']
        self.assertEqual(set(data), {'id', 'name', 'description', 'created_by', 'my_role', 'member_count', 'created_at'})
        self.assertEqual(data['name'], 'New Trip')
        self.assertEqual(data['my_role'], 'admin')
        self.assertEqual(data['member_count'], 1)
        self.assertTrue(GroupMembership.objects.filter(group_id=data['id'], user=self.owner, role='admin').exists())

    def test_create_atomic(self):
        with patch('groups.views.GroupMembership.objects.create', side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                self.client.post('/api/v1/groups/', {'name': 'Rollback'}, format='json')
        self.assertFalse(Group.objects.filter(name='Rollback').exists())

    def test_list_and_detail_visibility(self):
        self.assertEqual(self.client.get('/api/v1/groups/').data['count'], 1)
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.get('/api/v1/groups/').data['count'], 0)
        self.assertEqual(self.client.get(self.base).status_code, 404)
        self.assertEqual(self.client.get(self.base + 'members/').status_code, 404)
        self.assertEqual(self.invite().status_code, 404)

    def test_patch_admin_only_and_validation(self):
        self.assertEqual(self.client.patch(self.base, {'name': ' Updated ', 'description': 'Details'}, format='json').data['group']['name'], 'Updated')
        for payload in [{'name': ''}, {'name': ' '}, {'name': 'a'*101}, {'description': 'a'*501}]:
            with self.subTest(payload=payload):
                self.assertEqual(self.client.patch(self.base, payload, format='json').status_code, 400)
        self.client.force_authenticate(self.member)
        self.assertEqual(self.client.patch(self.base, {'name': 'No'}, format='json').status_code, 403)
        self.assertEqual(self.invite().status_code, 403)
        self.assertEqual(self.client.get(self.base + 'invitations/').status_code, 403)

    def test_staff_is_not_group_admin(self):
        self.member.is_staff = self.member.is_superuser = True
        self.member.save()
        self.client.force_authenticate(self.member)
        self.assertEqual(self.client.patch(self.base, {'name': 'No'}, format='json').status_code, 403)

    def test_security(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/v1/groups/').status_code, 401)
        self.owner.email_verified = False
        self.owner.save()
        self.client.force_authenticate(self.owner)
        response = self.client.get('/api/v1/groups/')
        self.assertEqual((response.status_code, response.data['code']), (403, 'EMAIL_NOT_VERIFIED'))

    def test_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.owner)
        response = client.post('/api/v1/groups/', {'name': 'Trip'}, format='json')
        self.assertEqual((response.status_code, response.json()['code']), (403, 'CSRF_FAILED'))
        client.get('/api/v1/auth/csrf/')
        response = client.post('/api/v1/groups/', {'name': 'Trip'}, format='json', HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 201)

    def test_member_shape_and_order(self):
        data = self.client.get(self.base + 'members/').data
        self.assertEqual(data['count'], 2)
        self.assertEqual(data['results'][0]['user']['id'], self.owner.pk)
        self.assertEqual(set(data['results'][0]), {'id', 'user', 'role', 'joined_at'})
        self.assertEqual(set(data['results'][0]['user']), {'id', 'username', 'full_name'})

    def test_invitation_create_conflicts_and_private_shape(self):
        response = self.invite()
        self.assertEqual(response.status_code, 201)
        data = response.data['invitation']
        self.assertEqual(set(data), {'id', 'group', 'invited_by', 'invitee', 'status', 'created_at'})
        self.assertEqual(set(data['invitee']), {'id', 'username'})
        self.assertEqual(self.invite().data['code'], 'INVITATION_ALREADY_PENDING')
        self.assertEqual(self.invite(self.member).data['code'], 'ALREADY_GROUP_MEMBER')
        self.assertEqual(self.invite(self.owner).status_code, 409)

    def test_invitation_target_indistinguishable(self):
        for active, verified in [(False, True), (True, False), (False, False)]:
            self.outsider.is_active, self.outsider.email_verified = active, verified
            self.outsider.save()
            self.assertEqual(self.invite().status_code, 404)
        self.assertEqual(self.client.post(self.base + 'invitations/', {'username': 'missing'}, format='json').status_code, 404)

    def test_accept_and_repeat(self):
        invitation = self.invite().data['invitation']['id']
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.action(invitation, 'accept').data['invitation']['status'], 'accepted')
        self.assertEqual(self.action(invitation, 'accept').status_code, 409)
        self.assertTrue(GroupMembership.objects.filter(group=self.group, user=self.outsider, status='active').exists())

    def test_decline_reinvite_cancel(self):
        invitation = self.invite().data['invitation']['id']
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.action(invitation, 'decline').status_code, 200)
        self.client.force_authenticate(self.owner)
        second = self.invite().data['invitation']['id']
        self.assertNotEqual(invitation, second)
        self.assertEqual(self.action(second, 'cancel').data['invitation']['status'], 'cancelled')
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.action(second, 'accept').status_code, 409)
        self.assertFalse(GroupMembership.objects.filter(group=self.group, user=self.outsider).exists())

    def test_invitation_visibility_and_authorization(self):
        invitation = self.invite().data['invitation']['id']
        self.assertEqual(self.client.get('/api/v1/invitations/').data['count'], 0)
        self.assertEqual(self.action(invitation, 'accept').status_code, 404)
        self.client.force_authenticate(self.member)
        self.assertEqual(self.action(invitation, 'decline').status_code, 404)
        self.assertEqual(self.action(invitation, 'cancel').status_code, 403)
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.get('/api/v1/invitations/').data['count'], 1)
        self.assertEqual(self.action(invitation, 'cancel').status_code, 404)

    def test_filter_before_pagination(self):
        GroupInvitation.objects.bulk_create([GroupInvitation(group=self.group, invited_by=self.owner, invitee=self.outsider, status='declined') for _ in range(21)])
        self.invite()
        for path in [self.base+'invitations/', '/api/v1/invitations/']:
            self.client.force_authenticate(self.owner if 'groups' in path else self.outsider)
            self.assertEqual(self.client.get(path, {'status': 'pending'}).data['count'], 1)
            result = self.client.get(path, {'status': 'declined'})
            self.assertEqual(result.data['count'], 21)
            self.assertEqual(len(result.data['results']), 20)
            self.assertIsNotNone(result.data['next'])
            invalid = self.client.get(path, {'status': 'invalid'})
            self.assertEqual(invalid.status_code, 400)
            self.assertIn('status', invalid.data['fields'])

    def test_remove_and_rejoin_same_membership(self):
        response = self.client.post(self.base+f'members/{self.member.pk}/remove/')
        self.assertEqual(response.status_code, 200)
        self.membership.refresh_from_db()
        self.assertEqual(self.membership.status, 'removed')
        self.assertIsNotNone(self.membership.removed_at)
        self.client.force_authenticate(self.member)
        self.assertEqual(self.client.get(self.base).status_code, 404)
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.get(self.base+'members/').data['count'], 1)
        invitation = self.invite(self.member).data['invitation']['id']
        self.client.force_authenticate(self.member)
        self.assertEqual(self.action(invitation, 'accept').status_code, 200)
        self.membership.refresh_from_db()
        self.assertEqual(self.membership.status, 'active')
        self.assertIsNone(self.membership.removed_at)
        self.assertEqual(GroupMembership.objects.filter(group=self.group, user=self.member).count(), 1)

    def test_removal_permissions_and_financial_block(self):
        self.assertEqual(self.client.post(self.base+f'members/{self.owner.pk}/remove/').status_code, 403)
        with patch('groups.views.has_active_financial_references', return_value=True):
            response = self.client.post(self.base+f'members/{self.member.pk}/remove/')
        self.assertEqual(response.data['code'], 'MEMBER_HAS_ACTIVE_FINANCIAL_REFERENCES')
        self.membership.refresh_from_db()
        self.assertEqual(self.membership.status, 'active')
        self.client.force_authenticate(self.member)
        self.assertEqual(self.client.post(self.base+f'members/{self.member.pk}/remove/').status_code, 403)

    def test_full_group_rejects_acceptance(self):
        members = [User(email=f'bulk{i}@example.com', username=f'bulk{i}', full_name='Bulk', email_verified=True) for i in range(98)]
        User.objects.bulk_create(members)
        GroupMembership.objects.bulk_create([GroupMembership(group=self.group, user=u, role='member') for u in members])
        invitation = self.invite().data['invitation']['id']
        self.client.force_authenticate(self.outsider)
        response = self.action(invitation, 'accept')
        self.assertEqual(response.data['code'], 'GROUP_MEMBER_LIMIT_REACHED')
        self.assertEqual(GroupInvitation.objects.get(pk=invitation).status, 'pending')

    def test_database_constraints(self):
        for data in [dict(user=self.member, role='member'), dict(user=self.outsider, role='admin'), dict(user=self.outsider, role='admin', status='removed')]:
            with self.subTest(data=data), self.assertRaises(IntegrityError), transaction.atomic():
                GroupMembership.objects.create(group=self.group, **data)
        self.invite()
        with self.assertRaises(IntegrityError), transaction.atomic():
            GroupInvitation.objects.create(group=self.group, invitee=self.outsider, invited_by=self.owner)

    def test_no_extra_apis(self):
        self.assertEqual(self.client.delete(self.base).status_code, 405)
        self.assertEqual(self.client.post(self.base+'leave/').status_code, 404)

    def test_admin_read_only(self):
        staff = user('staff', is_staff=True, is_superuser=True)
        request = RequestFactory().get('/admin/')
        request.user = staff
        for model in [Group, GroupMembership, GroupInvitation]:
            model_admin = admin.site._registry[model]
            self.assertTrue(model_admin.has_view_permission(request))
            self.assertFalse(model_admin.has_add_permission(request))
            self.assertFalse(model_admin.has_change_permission(request))
            self.assertFalse(model_admin.has_delete_permission(request))
            self.assertEqual(model_admin.get_actions(request), {})
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get('/admin/groups/group/').status_code, 302)


class ConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.owner = user('owner')
        self.first = user('first')
        self.second = user('second')
        self.group = Group.objects.create(name='Concurrent', created_by=self.owner)
        GroupMembership.objects.create(group=self.group, user=self.owner, role='admin')

    def race(self, jobs):
        self.assertEqual(connection.vendor, 'postgresql', 'These tests require real PostgreSQL locks')
        barrier = Barrier(len(jobs))

        def run(job):
            close_old_connections()
            try:
                client = APIClient()
                actor, path, data = job
                client.force_authenticate(actor)
                barrier.wait(timeout=10)
                return client.post(path, data, format='json').status_code
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            return list(pool.map(run, jobs))

    def invitation(self, actor):
        return GroupInvitation.objects.create(group=self.group, invitee=actor, invited_by=self.owner)

    def test_double_accept(self):
        invitation = self.invitation(self.first)
        job = (self.first, f'/api/v1/invitations/{invitation.pk}/accept/', {})
        self.assertEqual(sorted(self.race([job, job])), [200, 409])
        self.assertEqual(GroupMembership.objects.filter(group=self.group, user=self.first).count(), 1)
        self.assertEqual(GroupMembership.objects.filter(group=self.group, role='admin').count(), 1)

    def test_duplicate_invite(self):
        job = (self.owner, f'/api/v1/groups/{self.group.pk}/invitations/', {'username': self.first.username})
        self.assertEqual(sorted(self.race([job, job])), [201, 409])
        self.assertEqual(self.group.invitations.filter(status='pending').count(), 1)

    def test_last_slot(self):
        members = [User(email=f'fill{i}@example.com', username=f'fill{i}', full_name='Fill', email_verified=True) for i in range(98)]
        User.objects.bulk_create(members)
        GroupMembership.objects.bulk_create([GroupMembership(group=self.group, user=u, role='member') for u in members])
        invitations = [self.invitation(actor) for actor in [self.first, self.second]]
        jobs = [(actor, f'/api/v1/invitations/{inv.pk}/accept/', {}) for actor, inv in zip([self.first, self.second], invitations)]
        self.assertEqual(sorted(self.race(jobs)), [200, 409])
        self.assertEqual(self.group.memberships.filter(status='active').count(), 100)

    def test_accept_cancel_race(self):
        inv = self.invitation(self.first)
        statuses = self.race([(self.first, f'/api/v1/invitations/{inv.pk}/accept/', {}), (self.owner, f'/api/v1/invitations/{inv.pk}/cancel/', {})])
        self.assertEqual(sorted(statuses), [200, 409])
        inv.refresh_from_db()
        self.assertEqual(self.group.memberships.filter(user=self.first, status='active').exists(), inv.status == 'accepted')

    def test_double_remove(self):
        GroupMembership.objects.create(group=self.group, user=self.first, role='member')
        job = (self.owner, f'/api/v1/groups/{self.group.pk}/members/{self.first.pk}/remove/', {})
        self.assertEqual(sorted(self.race([job, job])), [200, 404])
        self.assertEqual(self.group.memberships.filter(role='admin', status='active').count(), 1)

class AdminHTTPTests(TestCase):
    def test_staff_and_superuser_cannot_mutate_models(self):
        owner = user('adminowner')
        group = Group.objects.create(name='Read only', created_by=owner)
        membership = GroupMembership.objects.create(group=group, user=owner, role='admin')
        invitee = user('admininvitee')
        invitation = GroupInvitation.objects.create(group=group, invited_by=owner, invitee=invitee)
        client = APIClient()
        client.force_login(user('superstaff', is_staff=True, is_superuser=True))
        for model, obj in [('group', group), ('groupmembership', membership), ('groupinvitation', invitation)]:
            root = f'/admin/groups/{model}/'
            self.assertEqual(client.get(root).status_code, 200)
            self.assertEqual(client.get(root+f'{obj.pk}/change/').status_code, 200)
            self.assertEqual(client.post(root+'add/', {}).status_code, 403)
            self.assertEqual(client.post(root+f'{obj.pk}/change/', {}).status_code, 403)
            self.assertEqual(client.post(root+f'{obj.pk}/delete/', {}).status_code, 403)
            client.post(root, {'action': 'delete_selected', '_selected_action': [str(obj.pk)]})
            self.assertTrue(type(obj).objects.filter(pk=obj.pk).exists())
        client.force_login(user('plainstaff', is_staff=True))
        self.assertEqual(client.get('/admin/groups/group/').status_code, 403)
