import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class Group(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(max_length=500, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='created_groups')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class GroupMembership(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='group_memberships')
    role = models.CharField(max_length=6, choices=[('admin', 'Admin'), ('member', 'Member')])
    status = models.CharField(max_length=7, choices=[('active', 'Active'), ('removed', 'Removed')], default='active')
    joined_at = models.DateTimeField(auto_now_add=True)
    removed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['group', 'user'], name='unique_group_user'),
            models.UniqueConstraint(fields=['group'], condition=Q(role='admin', status='active'), name='unique_active_group_admin'),
            models.CheckConstraint(condition=Q(role__in=['admin', 'member']), name='membership_valid_role'),
            models.CheckConstraint(condition=(Q(status='active', removed_at__isnull=True) | Q(status='removed', role='member', removed_at__isnull=False)), name='membership_valid_state'),
        ]
        indexes = [models.Index(fields=['user', 'group'])]


class GroupInvitation(models.Model):
    STATUS_CHOICES = [(s, s.title()) for s in ['pending', 'accepted', 'declined', 'cancelled']]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='invitations')
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='sent_group_invitations')
    invitee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='group_invitations')
    status = models.CharField(max_length=9, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['group', 'invitee'], condition=Q(status='pending'), name='unique_pending_group_invitation'),
            models.CheckConstraint(condition=Q(status__in=['pending', 'accepted', 'declined', 'cancelled']), name='invitation_valid_status'),
        ]
        indexes = [models.Index(fields=['group', 'status']), models.Index(fields=['invitee', 'status'])]
