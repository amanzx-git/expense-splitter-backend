from django.urls import path
from . import views

urlpatterns = [
    path('auth/csrf/', views.csrf_token_view, name='auth-csrf'),
    path('auth/register/', views.RegisterView.as_view(), name='auth-register'),
    path('auth/verify-email/', views.VerifyEmailView.as_view(), name='auth-verify-email'),
    path('auth/resend-verification/', views.ResendVerificationView.as_view(), name='auth-resend-verification'),
    path('auth/login/', views.LoginView.as_view(), name='auth-login'),
    path('auth/logout/', views.LogoutView.as_view(), name='auth-logout'),
    path('auth/password-reset/', views.PasswordResetView.as_view(), name='auth-password-reset'),
    path('auth/password-reset/confirm/', views.PasswordResetConfirmView.as_view(), name='auth-password-reset-confirm'),
    path('users/me/', views.MeView.as_view(), name='users-me'),
    path('users/me/photo/', views.PhotoView.as_view(), name='users-me-photo'),
    path('users/search/', views.UserSearchView.as_view(), name='users-search'),
]
