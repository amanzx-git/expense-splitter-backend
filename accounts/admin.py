
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm

from .models import User


class SplitterUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("email", "username", "full_name")


class SplitterUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = SplitterUserChangeForm
    add_form = SplitterUserCreationForm

    list_display = (
        "email",
        "username",
        "full_name",
        "email_verified",
        "is_active",
        "is_staff",
        "date_joined",
    )

    list_filter = (
        "email_verified",
        "is_active",
        "is_staff",
        "is_superuser",
    )

    search_fields = (
        "email",
        "username",
        "full_name",
    )

    ordering = ("email",)

    readonly_fields = (
        "id",
        "last_login",
        "date_joined",
    )

    fieldsets = (
        ("Account", {
            "fields": (
                "id",
                "email",
                "username",
                "password",
            ),
        }),
        ("Personal information", {
            "fields": (
                "full_name",
                "upi_id",
                "profile_photo",
            ),
        }),
        ("Verification and access", {
            "fields": (
                "email_verified",
                "is_active",
                "is_staff",
                "is_superuser",
            ),
        }),
        ("Permissions", {
            "fields": (
                "groups",
                "user_permissions",
            ),
        }),
        ("Important dates", {
            "fields": (
                "last_login",
                "date_joined",
            ),
        }),
    )

    add_fieldsets = (
        ("Create user", {
            "classes": ("wide",),
            "fields": (
                "email",
                "username",
                "full_name",
                "password1",
                "password2",
                "is_active",
                "is_staff",
            ),
        }),
    )

    filter_horizontal = ("groups", "user_permissions")

    # Only superusers can create or edit accounts in Admin.
    # Ordinary staff may receive explicit view permission.
    def has_add_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    # Do not allow user deletion through Admin.
    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions
