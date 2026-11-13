from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from accounts.views import ProtectedView
from .models import Group, GroupMembership, GroupInvitation
from .serializers import GroupInputSerializer, InviteInputSerializer, GroupSerializer, MembershipSerializer, InvitationSerializer
from .services import has_active_financial_references


class GroupAPI(ProtectedView):
    parser_classes = [JSONParser]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not request.user.email_verified:
            self.permission_denied(request, message='Verify your email before signing in.', code='EMAIL_NOT_VERIFIED')

    def handle_exception(self, exc):
        response = super().handle_exception(exc)
        if getattr(exc, 'get_codes', lambda: None)() == 'EMAIL_NOT_VERIFIED':
            response.data['code'] = 'EMAIL_NOT_VERIFIED'
        return response

    def group(self, group_id, admin=False, lock=False):
        qs = Group.objects.select_for_update() if lock else Group.objects.all()
        group = get_object_or_404(qs, pk=group_id)
        membership = group.memberships.filter(user=self.request.user, status='active').first()
        if not membership:
            raise NotFound()
        if admin and membership.role != 'admin':
            raise PermissionDenied()
        return group

    def listing(self, qs, serializer):
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(qs, self.request, view=self)
        return paginator.get_paginated_response(serializer(page, many=True, context={'request': self.request}).data)

    def group_response(self, group, status=200):
        return Response({'group': GroupSerializer(group, context={'request': self.request}).data}, status=status)


def conflict(code='API_ERROR', message='This operation conflicts with the current state.'):
    # R1.2 supplies no specific machine code for a non-pending invitation.
    return Response({'code': code, 'message': message}, status=409)


def filtered_invitations(qs, request):
    status = request.query_params.get('status')
    if status is not None:
        if status not in dict(GroupInvitation.STATUS_CHOICES):
            raise serializers.ValidationError({'status': ['Select a valid invitation status.']})
        qs = qs.filter(status=status)
    return qs.select_related('group', 'invitee', 'invited_by').order_by('-created_at', '-id')


class GroupListView(GroupAPI):
    def get(self, request):
        qs = Group.objects.filter(memberships__user=request.user, memberships__status='active').order_by('-created_at', '-id')
        return self.listing(qs, GroupSerializer)

    @transaction.atomic
    def post(self, request):
        serializer = GroupInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        group = Group.objects.create(created_by=request.user, **serializer.validated_data)
        GroupMembership.objects.create(group=group, user=request.user, role='admin')
        return self.group_response(group, 201)


class GroupDetailView(GroupAPI):
    def get(self, request, group_id):
        return self.group_response(self.group(group_id))

    @transaction.atomic
    def patch(self, request, group_id):
        group = self.group(group_id, admin=True, lock=True)
        serializer = GroupInputSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        for key, value in serializer.validated_data.items():
            setattr(group, key, value)
        group.save(update_fields=[*serializer.validated_data, 'updated_at'])
        return self.group_response(group)


class MembersView(GroupAPI):
    def get(self, request, group_id):
        group = self.group(group_id)
        return self.listing(group.memberships.filter(status='active').select_related('user').order_by('joined_at', 'user_id'), MembershipSerializer)


class RemoveMemberView(GroupAPI):
    @transaction.atomic
    def post(self, request, group_id, user_id):
        group = self.group(group_id, admin=True, lock=True)
        member = get_object_or_404(group.memberships.select_for_update(), user_id=user_id, status='active')
        if member.role == 'admin' or member.user_id == request.user.pk:
            raise PermissionDenied('The group administrator cannot be removed.')
        if has_active_financial_references(group, user_id):
            return conflict('MEMBER_HAS_ACTIVE_FINANCIAL_REFERENCES', 'This member has active financial references.')
        member.status = 'removed'
        member.removed_at = timezone.now()
        member.save(update_fields=['status', 'removed_at'])
        return Response({'message': 'Member removed'})


class GroupInvitationsView(GroupAPI):
    def get(self, request, group_id):
        group = self.group(group_id, admin=True)
        return self.listing(filtered_invitations(group.invitations.all(), request), InvitationSerializer)

    @transaction.atomic
    def post(self, request, group_id):
        group = self.group(group_id, admin=True, lock=True)
        serializer = InviteInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = get_object_or_404(get_user_model(), username=serializer.validated_data['username'].lower(), is_active=True, email_verified=True)
        if group.memberships.filter(user=user, status='active').exists():
            return conflict('ALREADY_GROUP_MEMBER', 'This user is already a member of the group.')
        if group.invitations.filter(invitee=user, status='pending').exists():
            return conflict('INVITATION_ALREADY_PENDING', 'An invitation is already pending for this user.')
        invitation = GroupInvitation.objects.create(group=group, invited_by=request.user, invitee=user)
        return Response({'invitation': InvitationSerializer(invitation).data}, status=201)


class InvitationListView(GroupAPI):
    def get(self, request):
        return self.listing(filtered_invitations(GroupInvitation.objects.filter(invitee=request.user), request), InvitationSerializer)


class InvitationActionView(GroupAPI):
    action = None

    @transaction.atomic
    def post(self, request, invitation_id):
        target = get_object_or_404(GroupInvitation.objects.only('group_id'), pk=invitation_id)
        group = get_object_or_404(Group.objects.select_for_update(), pk=target.group_id)
        invitation = get_object_or_404(GroupInvitation.objects.select_for_update(), pk=invitation_id, group=group)
        if self.action == 'cancel':
            self.group(group.pk, admin=True)
        elif invitation.invitee_id != request.user.pk:
            raise NotFound()
        if invitation.status != 'pending':
            return conflict(message='This invitation is no longer pending.')
        if self.action == 'accept':
            if group.memberships.filter(user=request.user, status='active').exists():
                return conflict('ALREADY_GROUP_MEMBER', 'This user is already a member of the group.')
            if group.memberships.filter(status='active').count() >= 100:
                return conflict('GROUP_MEMBER_LIMIT_REACHED', 'This group already has 100 active members.')
            member = group.memberships.filter(user=request.user).first()
            if member:
                member.status, member.role, member.removed_at = 'active', 'member', None
                member.joined_at = timezone.now()
                member.save(update_fields=['status', 'role', 'removed_at', 'joined_at'])
            else:
                GroupMembership.objects.create(group=group, user=request.user, role='member')
        invitation.status = {'accept': 'accepted', 'decline': 'declined', 'cancel': 'cancelled'}[self.action]
        invitation.responded_at = timezone.now()
        invitation.save(update_fields=['status', 'responded_at'])
        return Response({'invitation': InvitationSerializer(invitation).data})
