from rest_framework import serializers
from .models import Group, GroupMembership, GroupInvitation


class GroupInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    description = serializers.CharField(max_length=500, allow_blank=True, required=False, default='')


class InviteInputSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=30)


class GroupSerializer(serializers.ModelSerializer):
    my_role = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = ['id', 'name', 'description', 'created_by', 'my_role', 'member_count', 'created_at']

    def get_my_role(self, obj):
        return obj.memberships.get(user=self.context['request'].user, status='active').role

    def get_member_count(self, obj):
        return obj.memberships.filter(status='active').count()


class MembershipSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()

    class Meta:
        model = GroupMembership
        fields = ['id', 'user', 'role', 'joined_at']

    def get_user(self, obj):
        return {key: getattr(obj.user, key) for key in ['id', 'username', 'full_name']}


class InvitationSerializer(serializers.ModelSerializer):
    group = serializers.SerializerMethodField()
    invited_by = serializers.SerializerMethodField()
    invitee = serializers.SerializerMethodField()

    class Meta:
        model = GroupInvitation
        fields = ['id', 'group', 'invited_by', 'invitee', 'status', 'created_at']

    def get_group(self, obj):
        return {'id': obj.group_id, 'name': obj.group.name}

    def get_invited_by(self, obj):
        return {'id': obj.invited_by_id, 'username': obj.invited_by.username}

    def get_invitee(self, obj):
        return {'id': obj.invitee_id, 'username': obj.invitee.username}
