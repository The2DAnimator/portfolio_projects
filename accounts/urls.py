from django.urls import path
from django.urls import reverse_lazy
from django.contrib.auth import views as auth_views
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.Email2FALoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('register/', views.register, name='register'),
    path('api/users/<int:user_id>/toggle-follow/', views.toggle_follow, name='toggle_follow'),
    path('profile/<str:username>/', views.profile, name='profile'),
    path('security/two-factor/', views.email_2fa_setup, name='email_2fa_setup'),
    # Password change
    path(
        'password-change/',
        auth_views.PasswordChangeView.as_view(
            template_name='accounts/password_change.html',
            success_url=reverse_lazy('accounts:password_change_done'),
        ),
        name='password_change',
    ),
    path(
        'password-change/done/',
        auth_views.PasswordChangeDoneView.as_view(
            template_name='accounts/password_change_done.html'
        ),
        name='password_change_done',
    ),
    # Email 2FA verify
    path('security/email-verify/', views.email_2fa_verify, name='email_2fa_verify'),
    path('security/email-resend/', views.email_2fa_resend, name='email_2fa_resend'),
    path('security/edit-email/', views.edit_email, name='edit_email'),
]