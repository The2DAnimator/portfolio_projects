from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.http import JsonResponse, HttpResponseBadRequest
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import views as auth_views
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import Follow, UserSecuritySettings, Email2FAToken
from projects.models import Project
import random
from datetime import timedelta
from django.core.cache import cache

# Create your views here.

def register(request):
    if request.method == 'POST':
        # Throttle by IP: 5 attempts per 5 minutes
        ip = request.META.get('REMOTE_ADDR', 'unknown')
        key = f"throttle:register:{ip}"
        if _throttle(key, limit=5, window_seconds=300):
            messages.error(request, 'Too many registration attempts. Please try again later.')
            return redirect('accounts:register')
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Persist extra fields from template into the user profile
            user.first_name = request.POST.get('first_name', '').strip()
            user.last_name = request.POST.get('last_name', '').strip()
            user.email = request.POST.get('email', '').strip()
            user.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account created for {username}! You can now log in.')
            return redirect('accounts:login')
    else:
        form = UserCreationForm()
    return render(request, 'accounts/register.html', {'form': form})

@login_required
def toggle_follow(request, user_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)
    target = get_object_or_404(User, pk=user_id)
    if target == request.user:
        return JsonResponse({'error': 'Cannot follow yourself'}, status=400)
    follow, created = Follow.objects.get_or_create(user=request.user, target=target)
    if created:
        following = True
    else:
        follow.delete()
        following = False
    followers_count = Follow.objects.filter(target=target).count()
    return JsonResponse({'following': following, 'followers_count': followers_count})

def profile(request, username):
    user = get_object_or_404(User, username=username)
    # Public projects by this user
    projects = Project.objects.filter(owner=user, is_published=True).order_by('-created_at')
    followers_count = Follow.objects.filter(target=user).count()
    following_count = Follow.objects.filter(user=user).count()
    is_following = False
    if request.user.is_authenticated and request.user != user:
        is_following = Follow.objects.filter(user=request.user, target=user).exists()
    is_owner = request.user.is_authenticated and request.user == user
    context = {
        'profile_user': user,
        'projects': projects,
        'followers_count': followers_count,
        'following_count': following_count,
        'is_following': is_following,
        'is_owner': is_owner,
    }
    return render(request, 'accounts/profile.html', context)

@login_required
def two_factor_settings(request):
    return render(request, 'accounts/two_factor_settings.html')

def _get_security_settings(user: User) -> UserSecuritySettings:
    try:
        return user.security_settings
    except UserSecuritySettings.DoesNotExist:
        return UserSecuritySettings.objects.create(user=user)

def _generate_code() -> str:
    return f"{random.randint(0, 999999):06d}"

def _send_email_code(user: User, code: str) -> None:
    subject = 'Your verification code'
    message = f"Your verification code is: {code}. It will expire in 10 minutes."
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@example.com')
    recipient_list = [user.email]
    if user.email:
        send_mail(subject, message, from_email, recipient_list, fail_silently=True)

class Email2FALoginView(auth_views.LoginView):
    template_name = 'accounts/login.html'

    def post(self, request, *args, **kwargs):
        # Throttle login attempts by IP and username: 10 attempts per 10 minutes
        ip = request.META.get('REMOTE_ADDR', 'unknown')
        username = (request.POST.get('username') or '').strip() or 'unknown'
        if _throttle(f"throttle:login:ip:{ip}", limit=10, window_seconds=600) or \
           _throttle(f"throttle:login:user:{username}", limit=10, window_seconds=600):
            messages.error(request, 'Too many login attempts. Please wait and try again.')
            return self.form_invalid(self.get_form())
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        user = self.request.user
        # If 2FA via email is enabled, generate and send code then mark session unverified and redirect
        if user.is_authenticated:
            sec = _get_security_settings(user)
            if sec.email_2fa_enabled:
                code = _generate_code()
                expires_at = timezone.now() + timezone.timedelta(minutes=10)
                Email2FAToken.objects.create(user=user, code=code, expires_at=expires_at)
                _send_email_code(user, code)
                self.request.session['email_2fa_verified'] = False
                self.request.session['email_2fa_started_at'] = timezone.now().isoformat()
                return redirect('accounts:email_2fa_verify')
        return response

@login_required
def email_2fa_setup(request):
    sec = _get_security_settings(request.user)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'enable':
            if not request.user.email:
                messages.error(request, 'Add an email to your account before enabling 2FA.')
                return redirect('accounts:email_2fa_setup')
            sec.email_2fa_enabled = True
            sec.save()
            messages.success(request, 'Email two-factor authentication enabled.')
        elif action == 'disable':
            sec.email_2fa_enabled = False
            sec.save()
            messages.success(request, 'Email two-factor authentication disabled.')
        else:
            return HttpResponseBadRequest('Invalid action')
        return redirect('accounts:email_2fa_setup')
    return render(request, 'accounts/email_2fa_setup.html', { 'security': sec })

@login_required
def email_2fa_verify(request):
    sec = _get_security_settings(request.user)
    if not sec.email_2fa_enabled:
        return redirect(settings.LOGIN_REDIRECT_URL)
    # On GET, send a new code if none recently
    if request.method == 'GET':
        # Optionally re-send on GET
        recent = Email2FAToken.objects.filter(user=request.user, is_used=False, expires_at__gt=timezone.now()).order_by('-created_at').first()
        if not recent:
            code = _generate_code()
            expires_at = timezone.now() + timezone.timedelta(minutes=10)
            Email2FAToken.objects.create(user=request.user, code=code, expires_at=expires_at)
            _send_email_code(request.user, code)
        return render(request, 'accounts/email_2fa_verify.html')
    # POST: verify code
    # Throttle per-user: 6 attempts per 10 minutes
    if _throttle(f"throttle:2fa_verify:user:{request.user.id}", limit=6, window_seconds=600):
        messages.error(request, 'Too many verification attempts. Please wait and try again.')
        return redirect('accounts:email_2fa_verify')
    code = request.POST.get('code', '').strip()
    token = Email2FAToken.objects.filter(user=request.user, code=code, is_used=False, expires_at__gt=timezone.now()).order_by('-created_at').first()
    if not code or not token:
        messages.error(request, 'Invalid or expired code.')
        return redirect('accounts:email_2fa_verify')
    token.is_used = True
    token.save(update_fields=['is_used'])
    request.session['email_2fa_verified'] = True
    return redirect(settings.LOGIN_REDIRECT_URL)

@login_required
def email_2fa_resend(request):
    sec = _get_security_settings(request.user)
    if not sec.email_2fa_enabled or not request.user.email:
        messages.error(request, 'Email 2FA is not enabled or no email is set.')
        return redirect('accounts:email_2fa_setup')
    # throttle: 60 seconds since last token creation
    now = timezone.now()
    recent = Email2FAToken.objects.filter(user=request.user, is_used=False).order_by('-created_at').first()
    if recent and (now - recent.created_at) < timedelta(seconds=60):
        remaining = 60 - int((now - recent.created_at).total_seconds())
        if remaining < 0:
            remaining = 0
        messages.warning(request, f'Please wait {remaining}s before requesting a new code.')
        return redirect('accounts:email_2fa_verify')
    # Global throttle per-user: max 3 resends per 10 minutes
    if _throttle(f"throttle:2fa_resend:user:{request.user.id}", limit=3, window_seconds=600):
        messages.error(request, 'Too many resend attempts. Please try again later.')
        return redirect('accounts:email_2fa_verify')
    code = _generate_code()
    expires_at = now + timezone.timedelta(minutes=10)
    Email2FAToken.objects.create(user=request.user, code=code, expires_at=expires_at)
    _send_email_code(request.user, code)
    messages.success(request, 'A new verification code has been sent to your email.')
    return redirect('accounts:email_2fa_verify')

def _throttle(key: str, limit: int, window_seconds: int) -> bool:
    """Return True if over the limit within the sliding window; otherwise record and return False."""
    now_ts = timezone.now().timestamp()
    entries = cache.get(key) or []
    # keep only entries within window
    entries = [t for t in entries if (now_ts - t) < window_seconds]
    if len(entries) >= limit:
        # ensure key doesn't expire earlier than window
        cache.set(key, entries, timeout=window_seconds)
        return True
    entries.append(now_ts)
    cache.set(key, entries, timeout=window_seconds)
    return False

@login_required
def edit_email(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        if not email:
            messages.error(request, 'Email cannot be empty.')
        else:
            request.user.email = email
            request.user.save(update_fields=['email'])
            messages.success(request, 'Email updated successfully.')
            return redirect('accounts:email_2fa_setup')
    return render(request, 'accounts/edit_email.html')