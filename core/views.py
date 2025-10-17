from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth, TruncDay
from django.utils import timezone
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
import json
from projects.models import Project, ProjectLike, Category, ProjectImage, ProjectFile, PackageMockup
from accounts.models import Follow, UserStorageSettings
from .models import Message, RequestLog, DeviceLocation

def home(request):
    # Get featured projects (published projects with cover images)
    featured_projects = (
        Project.objects.filter(is_published=True)
        .exclude(cover_image='')
        .annotate(likes_count=Count('likes'))
        .order_by('-created_at')[:9]
    )

    # Precompute liked project ids for current user
    liked_project_ids = set()
    followed_user_ids = set()
    if request.user.is_authenticated:
        liked_project_ids = set(
            ProjectLike.objects.filter(user=request.user, project__in=featured_projects)
            .values_list('project_id', flat=True)
        )
        owner_ids = set(featured_projects.values_list('owner_id', flat=True))
        followed_user_ids = set(
            Follow.objects.filter(user=request.user, target_id__in=owner_ids)
            .values_list('target_id', flat=True)
        )
    
    # Get statistics
    total_projects = Project.objects.filter(is_published=True).count()
    total_users = User.objects.count()
    
    context = {
        'featured_projects': featured_projects,
        'liked_project_ids': liked_project_ids,
        'followed_user_ids': followed_user_ids,
        'total_projects': total_projects,
        'total_users': total_users,
    }
    
    return render(request, 'core/home.html', context)

def privacy(request):
    return render(request, 'core/privacy.html')

def terms(request):
    return render(request, 'core/terms.html')

def help_center(request):
    return render(request, 'core/help.html')

def contact(request):
    return render(request, 'core/contact.html')

def _storage_usage_bytes(user):
    total = 0
    try:
        # Projects media
        for p in Project.objects.filter(owner=user):
            for f in [p.cover_image, p.video_file, p.audio_file]:
                try:
                    if f and getattr(f, 'name', None):
                        size = getattr(f, 'size', None)
                        if size is None:
                            from django.core.files.storage import default_storage
                            if default_storage.exists(f.name):
                                size = default_storage.size(f.name)
                        if size:
                            total += int(size)
                except Exception:
                    continue
        # Project images
        for pi in ProjectImage.objects.filter(project__owner=user):
            try:
                f = pi.image
                if f and getattr(f, 'name', None):
                    size = getattr(f, 'size', None)
                    if size is None:
                        from django.core.files.storage import default_storage
                        if default_storage.exists(f.name):
                            size = default_storage.size(f.name)
                    if size:
                        total += int(size)
            except Exception:
                continue
        # Project files
        for pf in ProjectFile.objects.filter(project__owner=user):
            try:
                f = pf.file
                if f and getattr(f, 'name', None):
                    size = getattr(f, 'size', None)
                    if size is None:
                        from django.core.files.storage import default_storage
                        if default_storage.exists(f.name):
                            size = default_storage.size(f.name)
                    if size:
                        total += int(size)
            except Exception:
                continue
        # Mockups
        for m in PackageMockup.objects.filter(owner=user):
            for f in [m.container_image, m.design_image, m.generated_image, m.mask_image]:
                try:
                    if f and getattr(f, 'name', None):
                        size = getattr(f, 'size', None)
                        if size is None:
                            from django.core.files.storage import default_storage
                            if default_storage.exists(f.name):
                                size = default_storage.size(f.name)
                        if size:
                            total += int(size)
                except Exception:
                    continue
    except Exception:
        return total
    return total

@login_required
def admin_storage(request):
    if not request.user.is_staff:
        return redirect('core:home')
    # Update quota
    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip()
        user_id = request.POST.get('user_id')
        if action in ['set_quota', 'reset_quota']:
            quota_str = (request.POST.get('quota_mb') or '').strip()
            try:
                target = get_object_or_404(User, pk=int(user_id))
                uss, _ = UserStorageSettings.objects.get_or_create(user=target)
                if action == 'reset_quota' or quota_str == '':
                    uss.quota_mb = None
                else:
                    uss.quota_mb = int(quota_str)
                uss.save()
                messages.success(request, f"Updated storage quota for @{target.username}.")
            except Exception:
                messages.error(request, "Failed to update storage quota.")
        elif action == 'clear_locations':
            try:
                target = get_object_or_404(User, pk=int(user_id))
                deleted, _ = DeviceLocation.objects.filter(user=target).delete()
                messages.success(request, f"Cleared {deleted} device location entries for @{target.username}.")
            except Exception:
                messages.error(request, "Failed to clear device locations.")
        elif action == 'clear_logs':
            try:
                target = get_object_or_404(User, pk=int(user_id))
                deleted, _ = RequestLog.objects.filter(user=target).delete()
                messages.success(request, f"Cleared {deleted} request log entries for @{target.username}.")
            except Exception:
                messages.error(request, "Failed to clear request logs.")
        return redirect('core:admin_storage')

    # Bulk actions
    if request.method == 'POST' and (request.POST.get('action') or '').startswith('bulk_'):
        ids = request.POST.getlist('user_ids')
        action = request.POST.get('action')
        try:
            users_qs = User.objects.filter(id__in=[int(i) for i in ids if i])
            total = users_qs.count()
            if action == 'bulk_reset_quota':
                for u in users_qs:
                    uss, _ = UserStorageSettings.objects.get_or_create(user=u)
                    uss.quota_mb = None
                    uss.save()
                messages.success(request, f"Reset quota to default for {total} users.")
            elif action == 'bulk_clear_locations':
                deleted = 0
                for u in users_qs:
                    d, _ = DeviceLocation.objects.filter(user=u).delete()
                    deleted += d
                messages.success(request, f"Cleared {deleted} device locations across {total} users.")
            elif action == 'bulk_clear_logs':
                deleted = 0
                for u in users_qs:
                    d, _ = RequestLog.objects.filter(user=u).delete()
                    deleted += d
                messages.success(request, f"Cleared {deleted} request logs across {total} users.")
        except Exception:
            messages.error(request, "Bulk action failed.")
        return redirect('core:admin_storage')

    # List users with usage and quota
    q = (request.GET.get('q') or '').strip()
    users = User.objects.all()
    if q:
        users = users.filter(Q(username__icontains=q) | Q(email__icontains=q))
    # Compute usage for page users only to avoid heavy load
    page_size = int(request.GET.get('page_size') or 10)
    paginator = Paginator(users.order_by('username'), page_size)
    page_number = request.GET.get('page') or 1
    page_obj = paginator.get_page(page_number)
    usage_data = []
    default_quota_mb = int(getattr(__import__('django.conf').conf.settings, 'USER_STORAGE_QUOTA_MB', 0) or 0)
    for u in page_obj.object_list:
        used = _storage_usage_bytes(u)
        uss = UserStorageSettings.objects.filter(user=u).only('quota_mb').first()
        quota_mb = int(uss.quota_mb) if (uss and uss.quota_mb) else default_quota_mb
        quota_bytes = quota_mb * 1024 * 1024 if quota_mb else 0
        pct = 0
        if quota_bytes > 0:
            pct = min(100, int((used / quota_bytes) * 100)) if used else 0
        usage_data.append({
            'user': u,
            'used_mb': round(used / (1024*1024), 2),
            'quota_mb': quota_mb,
            'percent': pct,
        })
    # Summary stats (based on entire user set, not just page)
    # Note: for performance, compute approx using current page for now.
    total_users = users.count()
    avg_usage = 0.0
    near_quota = 0
    if usage_data:
        avg_usage = round(sum(d['used_mb'] for d in usage_data) / len(usage_data), 2)
        near_quota = sum(1 for d in usage_data if d['percent'] >= 80)
    context = {
        'page_obj': page_obj,
        'usage_data': usage_data,
        'q': q,
        'page_size': page_size,
        'default_quota_mb': default_quota_mb,
        'page_sizes': [10, 20, 50, 100],
        'total_users': total_users,
        'avg_usage': avg_usage,
        'near_quota': near_quota,
    }
    return render(request, 'core/admin_storage.html', context)

@login_required
def admin_analytics(request):
    if not request.user.is_staff:
        return redirect('core:home')
    if request.method == 'POST':
        act = (request.POST.get('action') or '').strip()
        try:
            if act == 'purge_all_logs':
                deleted, _ = RequestLog.objects.all().delete()
                messages.success(request, f"Purged {deleted} request logs.")
            elif act == 'purge_all_locations':
                deleted, _ = DeviceLocation.objects.all().delete()
                messages.success(request, f"Purged {deleted} device locations.")
            elif act == 'purge_older':
                days = int(request.POST.get('days') or '90')
                cutoff = timezone.now() - timezone.timedelta(days=days)
                d1, _ = RequestLog.objects.filter(created_at__lt=cutoff).delete()
                d2, _ = DeviceLocation.objects.filter(created_at__lt=cutoff).delete()
                messages.success(request, f"Purged {d1} logs and {d2} locations older than {days} days.")
        except Exception:
            messages.error(request, "Purge action failed.")
        return redirect('core:admin_analytics')
    period_days = request.GET.get('period') or '30'
    exclude_staff = (request.GET.get('exclude_staff') == '1')
    hide_i18n = (request.GET.get('hide_i18n') == '1')
    hide_query = (request.GET.get('hide_query') == '1')
    try:
        days = int(period_days)
    except Exception:
        days = 30
    since = timezone.now() - timezone.timedelta(days=days)

    qs = RequestLog.objects.filter(created_at__gte=since)
    if exclude_staff:
        qs = qs.exclude(user__is_staff=True)
    if hide_i18n:
        qs = qs.exclude(path__startswith='/i18n/').exclude(path__regex=r'^/([a-z]{2})(/|$)')

    total_requests = qs.count()
    unique_users = qs.exclude(user__isnull=True).values('user').distinct().count()
    unique_countries = qs.exclude(country='').values('country').distinct().count()
    errors = qs.filter(status__gte=400).count()
    error_rate = round((errors / total_requests) * 100.0, 2) if total_requests else 0.0
    # By country
    by_country = (
        qs.values('country')
          .annotate(count=Count('id'))
          .order_by('-count')[:20]
    )
    # By region
    by_region = (
        qs.values('country', 'region')
          .annotate(count=Count('id'))
          .order_by('-count')[:20]
    )
    # By user
    by_user = (
        qs.values('user__username')
          .annotate(count=Count('id'))
          .order_by('-count')[:20]
    )
    # Top paths (cleaned)
    from django.db.models import F, Value, Func
    class SplitPart(Func):
        function = 'SUBSTR'
    # Clean paths in Python for portability
    all_paths = qs.values_list('path', flat=True)
    cleaned = []
    for p in all_paths:
        if not p:
            continue
        base = p.split('?', 1)[0] if hide_query else p
        # strip language prefix /en/ or /sw/
        parts = base.split('/')
        if len(parts) > 2 and len(parts[1]) == 2:
            base = '/' + '/'.join(parts[2:])
        cleaned.append(base)
    from collections import Counter
    counter = Counter(cleaned)
    top_paths = [{'path': k, 'count': v} for k, v in counter.most_common(20)]
    # Status codes
    statuses = (
        qs.values('status')
          .annotate(count=Count('id'))
          .order_by('-count')
    )
    # Buckets for donut chart
    buckets = {'2xx': 0, '3xx': 0, '4xx': 0, '5xx': 0}
    for row in statuses:
        s = int(row['status'] or 0)
        if 200 <= s < 300:
            buckets['2xx'] += row['count']
        elif 300 <= s < 400:
            buckets['3xx'] += row['count']
        elif 400 <= s < 500:
            buckets['4xx'] += row['count']
        elif 500 <= s < 600:
            buckets['5xx'] += row['count']

    # Chart data (countries)
    labels = []
    counts = []
    if by_country:
        for row in by_country:
            labels.append(row['country'] or 'Unknown')
            counts.append(row['count'])
    # Time series per day
    per_day = (
        qs.annotate(d=TruncDay('created_at'))
          .values('d')
          .annotate(count=Count('id'))
          .order_by('d')
    )
    ts_labels = [r['d'].strftime('%Y-%m-%d') for r in per_day]
    ts_counts = [r['count'] for r in per_day]
    donut_labels = list(buckets.keys())
    donut_counts = list(buckets.values())

    context = {
        'period': str(days),
        'total_requests': total_requests,
        'unique_users': unique_users,
        'unique_countries': unique_countries,
        'error_rate': error_rate,
        'exclude_staff': exclude_staff,
        'hide_i18n': hide_i18n,
        'hide_query': hide_query,
        'by_country': by_country,
        'by_region': by_region,
        'by_user': by_user,
        'top_paths': top_paths,
        'statuses': statuses,
        'chart_labels_json': json.dumps(labels),
        'chart_counts_json': json.dumps(counts),
        'ts_labels_json': json.dumps(ts_labels),
        'ts_counts_json': json.dumps(ts_counts),
        'donut_labels_json': json.dumps(donut_labels),
        'donut_counts_json': json.dumps(donut_counts),
    }
    return render(request, 'core/admin_analytics.html', context)

@login_required
@require_POST
def api_device_location(request):
    try:
        lat = request.POST.get('latitude') or request.POST.get('lat')
        lng = request.POST.get('longitude') or request.POST.get('lon') or request.POST.get('lng')
        acc = request.POST.get('accuracy') or request.POST.get('accuracy_m')
        if not lat or not lng:
            # Try JSON body
            try:
                data = json.loads(request.body.decode('utf-8'))
                lat = lat or data.get('latitude') or data.get('lat')
                lng = lng or data.get('longitude') or data.get('lon') or data.get('lng')
                acc = acc or data.get('accuracy') or data.get('accuracy_m')
            except Exception:
                pass
        lat = float(lat)
        lng = float(lng)
        accuracy_m = float(acc) if acc is not None and acc != '' else None
    except Exception:
        return JsonResponse({'ok': False, 'error': 'invalid_payload'}, status=400)

    ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or request.META.get('REMOTE_ADDR') or None
    ua = (request.META.get('HTTP_USER_AGENT') or '')[:256]
    try:
        DeviceLocation.objects.create(
            user=request.user,
            latitude=lat,
            longitude=lng,
            accuracy_m=accuracy_m,
            ip=ip,
            user_agent=ua,
        )
        return JsonResponse({'ok': True})
    except Exception:
        return JsonResponse({'ok': False}, status=500)

@login_required
def get_conversation(request, user_id):
    other = get_object_or_404(User, pk=user_id)
    msgs = Message.objects.filter(
        Q(sender=request.user, recipient=other) |
        Q(sender=other, recipient=request.user)
    ).order_by('created_at')
    data = [
        {
            'id': m.id,
            'sender': m.sender.username,
            'recipient': m.recipient.username,
            'body': m.body,
            'created_at': m.created_at.strftime('%Y-%m-%d %H:%M')
        }
        for m in msgs
    ]
    return JsonResponse({'messages': data})

@login_required
def send_message(request, user_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)
    other = get_object_or_404(User, pk=user_id)
    body = (request.POST.get('body') or '').strip()
    if not body:
        return JsonResponse({'error': 'Message body required'}, status=400)
    m = Message.objects.create(sender=request.user, recipient=other, body=body)
    return JsonResponse({
        'id': m.id,
        'sender': m.sender.username,
        'recipient': m.recipient.username,
        'body': m.body,
        'created_at': m.created_at.strftime('%Y-%m-%d %H:%M')
    })

@login_required
def admin_dashboard(request):
    if not request.user.is_staff:
        return redirect('core:home')

    now = timezone.now()
    total_users = User.objects.count()
    total_projects = Project.objects.count()
    published_projects = Project.objects.filter(is_published=True).count()
    draft_projects = total_projects - published_projects
    total_likes = ProjectLike.objects.count()

    recent_users = User.objects.order_by('-date_joined')[:8]
    recent_projects = Project.objects.order_by('-created_at')[:8]

    # Projects per month (last 6 months)
    six_months_ago = (now.replace(day=1) - timezone.timedelta(days=180)).replace(day=1)
    monthly = (
        Project.objects.filter(created_at__gte=six_months_ago)
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )
    chart_labels = [m['month'].strftime('%b %Y') for m in monthly]
    chart_counts = [m['count'] for m in monthly]
    chart_labels_json = json.dumps(chart_labels)
    chart_counts_json = json.dumps(chart_counts)

    # Insights (likes): period filter and widgets
    period = (request.GET.get('period') or '30').strip()
    period_map = {'7': 7, '30': 30, '90': 90}
    since = None
    if period in period_map:
        since = now - timezone.timedelta(days=period_map[period])

    recent_likes_qs = ProjectLike.objects.select_related('user', 'project').order_by('-created_at')
    if since:
        recent_likes_qs = recent_likes_qs.filter(created_at__gte=since)
    recent_likes = list(recent_likes_qs[:10])

    top_liked_qs = Project.objects.all()
    if since:
        top_liked_qs = top_liked_qs.filter(likes__created_at__gte=since)
    top_liked = (
        top_liked_qs
        .annotate(likes_count=Count('likes'))
        .order_by('-likes_count', '-created_at')[:10]
    )

    context = {
        'total_users': total_users,
        'total_projects': total_projects,
        'published_projects': published_projects,
        'draft_projects': draft_projects,
        'total_likes': total_likes,
        'recent_users': recent_users,
        'recent_projects': recent_projects,
        'chart_labels_json': chart_labels_json,
        'chart_counts_json': chart_counts_json,
        'period': period,
        'recent_likes': recent_likes,
        'top_liked': top_liked,
    }
    return render(request, 'core/admin_dashboard.html', context)

@login_required
@require_POST
def admin_user_toggle_active(request, user_id):
    if not request.user.is_staff:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    target = get_object_or_404(User, pk=user_id)
    if target == request.user:
        return JsonResponse({'error': 'Cannot change your own active state'}, status=400)
    target.is_active = not target.is_active
    target.save(update_fields=['is_active'])
    return JsonResponse({'ok': True, 'is_active': target.is_active})

@login_required
@require_POST
def admin_user_toggle_staff(request, user_id):
    if not request.user.is_staff:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    target = get_object_or_404(User, pk=user_id)
    if target == request.user:
        return JsonResponse({'error': 'Cannot change your own staff state'}, status=400)
    target.is_staff = not target.is_staff
    target.save(update_fields=['is_staff'])
    return JsonResponse({'ok': True, 'is_staff': target.is_staff})

@login_required
def admin_projects(request):
    if not request.user.is_staff:
        return redirect('core:home')

    qs = Project.objects.select_related('owner').all()

    # Filters
    q = (request.GET.get('q') or '').strip()
    project_type = request.GET.get('type') or ''
    owner = (request.GET.get('owner') or '').strip()
    date_from = request.GET.get('from') or ''
    date_to = request.GET.get('to') or ''
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if project_type:
        qs = qs.filter(project_type=project_type)
    if owner:
        qs = qs.filter(owner__username__icontains=owner)
    if date_from:
        try:
            qs = qs.filter(created_at__date__gte=date_from)
        except Exception:
            pass
    if date_to:
        try:
            qs = qs.filter(created_at__date__lte=date_to)
        except Exception:
            pass

    # Sorting
    sort = request.GET.get('sort') or 'created_at'
    direction = request.GET.get('dir') or 'desc'
    allowed = {
        'title': 'title',
        'created_at': 'created_at',
        'is_published': 'is_published',
        'owner': 'owner__username',
        'project_type': 'project_type',
    }
    order_field = allowed.get(sort, 'created_at')
    if direction == 'desc':
        order_field = f'-{order_field}'
    qs = qs.order_by(order_field)

    # Pagination
    page_size = int(request.GET.get('page_size') or 10)
    paginator = Paginator(qs, page_size)
    page_number = request.GET.get('page') or 1
    page_obj = paginator.get_page(page_number)

    # For filter dropdown
    type_choices = [t[0] for t in Project.PROJECT_TYPES]

    context = {
        'q': q,
        'type_filter': project_type,
        'owner': owner,
        'date_from': date_from,
        'date_to': date_to,
        'sort': sort,
        'dir': direction,
        'page_obj': page_obj,
        'page_size': page_size,
        'total_projects': paginator.count,
        'type_choices': type_choices,
    }
    return render(request, 'core/admin_projects.html', context)

@login_required
@require_POST
def admin_projects_bulk(request):
    if not request.user.is_staff:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    action = request.POST.get('action')
    ids = request.POST.getlist('ids[]') or request.POST.getlist('ids')
    if not action or not ids:
        return JsonResponse({'error': 'Invalid request'}, status=400)
    qs = Project.objects.filter(id__in=ids)
    count = qs.count()
    if action == 'publish':
        qs.update(is_published=True)
    elif action == 'unpublish':
        qs.update(is_published=False)
    elif action == 'delete':
        qs.delete()
    else:
        return JsonResponse({'error': 'Unknown action'}, status=400)
    return JsonResponse({'ok': True, 'count': count})

@login_required
@require_POST
def admin_project_publish(request, project_id):
    if not request.user.is_staff:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    p = get_object_or_404(Project, pk=project_id)
    p.is_published = True
    p.save(update_fields=['is_published'])
    return JsonResponse({'ok': True})

@login_required
@require_POST
def admin_project_unpublish(request, project_id):
    if not request.user.is_staff:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    p = get_object_or_404(Project, pk=project_id)
    p.is_published = False
    p.save(update_fields=['is_published'])
    return JsonResponse({'ok': True})

@login_required
@require_POST
def admin_project_delete(request, project_id):
    if not request.user.is_staff:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    p = get_object_or_404(Project, pk=project_id)
    p.delete()
    return JsonResponse({'ok': True})

@login_required
def admin_users(request):
    if not request.user.is_staff:
        return redirect('core:home')

    # Search
    q = (request.GET.get('q') or '').strip()
    users = User.objects.all()
    if q:
        users = users.filter(Q(username__icontains=q) | Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q))

    # Sorting
    sort = request.GET.get('sort') or 'date_joined'
    direction = request.GET.get('dir') or 'desc'
    allowed = {
        'username': 'username',
        'email': 'email',
        'date_joined': 'date_joined',
        'is_active': 'is_active',
        'is_staff': 'is_staff',
    }
    order_field = allowed.get(sort, 'date_joined')
    if direction == 'desc':
        order_field = f'-{order_field}'
    users = users.order_by(order_field)

    # Pagination
    page_size = int(request.GET.get('page_size') or 10)
    paginator = Paginator(users, page_size)
    page_number = request.GET.get('page') or 1
    page_obj = paginator.get_page(page_number)

    context = {
        'q': q,
        'sort': sort,
        'dir': direction,
        'page_obj': page_obj,
        'page_size': page_size,
        'total_users': paginator.count,
    }
    return render(request, 'core/admin_users.html', context)

@login_required
@require_POST
def admin_users_bulk(request):
    if not request.user.is_staff:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    action = request.POST.get('action')
    ids = request.POST.getlist('ids[]') or request.POST.getlist('ids')
    if not action or not ids:
        return JsonResponse({'error': 'Invalid request'}, status=400)
    qs = User.objects.filter(id__in=ids)
    # Prevent modifying the current user in bulk
    qs = qs.exclude(id=request.user.id)
    if action == 'deactivate':
        qs.update(is_active=False)
    elif action == 'activate':
        qs.update(is_active=True)
    else:
        return JsonResponse({'error': 'Unknown action'}, status=400)
    return JsonResponse({'ok': True, 'count': qs.count()})

@login_required
def admin_categories(request):
    if not request.user.is_staff:
        return redirect('core:home')
    q = (request.GET.get('q') or '').strip()
    cats = Category.objects.all()
    if q:
        cats = cats.filter(Q(name__icontains=q) | Q(description__icontains=q))
    sort = request.GET.get('sort') or 'name'
    direction = request.GET.get('dir') or 'asc'
    allowed = {'name': 'name', 'created': 'id'}
    order_field = allowed.get(sort, 'name')
    if direction == 'desc':
        order_field = f'-{order_field}'
    cats = cats.order_by(order_field)
    page_size = int(request.GET.get('page_size') or 10)
    paginator = Paginator(cats, page_size)
    page_number = request.GET.get('page') or 1
    page_obj = paginator.get_page(page_number)
    context = {
        'q': q,
        'sort': sort,
        'dir': direction,
        'page_obj': page_obj,
        'page_size': page_size,
        'total_categories': paginator.count,
    }
    return render(request, 'core/admin_categories.html', context)

@login_required
def admin_category_create(request):
    if not request.user.is_staff:
        return redirect('core:home')
    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()
        description = (request.POST.get('description') or '').strip()
        if not name:
            messages.error(request, 'Name is required.')
        else:
            Category.objects.create(name=name, description=description)
            messages.success(request, 'Category created.')
            return redirect('core:admin_categories')
    return render(request, 'core/admin_category_form.html', { 'mode': 'create' })

@login_required
def admin_category_edit(request, category_id):
    if not request.user.is_staff:
        return redirect('core:home')
    cat = get_object_or_404(Category, pk=category_id)
    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()
        description = (request.POST.get('description') or '').strip()
        if not name:
            messages.error(request, 'Name is required.')
        else:
            cat.name = name
            cat.description = description
            cat.save(update_fields=['name', 'description'])
            messages.success(request, 'Category updated.')
            return redirect('core:admin_categories')
    return render(request, 'core/admin_category_form.html', { 'mode': 'edit', 'category': cat })

@login_required
@require_POST
def admin_category_delete(request, category_id):
    if not request.user.is_staff:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    cat = get_object_or_404(Category, pk=category_id)
    cat.delete()
    return JsonResponse({'ok': True})