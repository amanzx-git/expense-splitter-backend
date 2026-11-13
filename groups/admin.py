from django.contrib import admin
from .models import Group, GroupMembership, GroupInvitation


class ReadOnlyGroupAdmin(admin.ModelAdmin):
    actions = None

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Group)
class GroupAdmin(ReadOnlyGroupAdmin):
    list_display = ['id', 'name', 'created_by', 'created_at']
    search_fields = ['name']


@admin.register(GroupMembership)
class MembershipAdmin(ReadOnlyGroupAdmin):
    list_display = ['id', 'group', 'user', 'role', 'status']
    list_filter = ['role', 'status']


@admin.register(GroupInvitation)
class InvitationAdmin(ReadOnlyGroupAdmin):
    list_display = ['id', 'group', 'invitee', 'status']
    list_filter = ['status']
