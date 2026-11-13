from django.urls import path
from .views import GroupListView, GroupDetailView, MembersView, RemoveMemberView, GroupInvitationsView, InvitationListView, InvitationActionView

urlpatterns = [
    path('groups/', GroupListView.as_view()),
    path('groups/<uuid:group_id>/', GroupDetailView.as_view()),
    path('groups/<uuid:group_id>/members/', MembersView.as_view()),
    path('groups/<uuid:group_id>/members/<uuid:user_id>/remove/', RemoveMemberView.as_view()),
    path('groups/<uuid:group_id>/invitations/', GroupInvitationsView.as_view()),
    path('invitations/', InvitationListView.as_view()),
    *[path('invitations/<uuid:invitation_id>/' + action + '/', InvitationActionView.as_view(action=action)) for action in ['accept', 'decline', 'cancel']],
]
