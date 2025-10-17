import logging
from django.conf import settings
from django.http import HttpResponseForbidden
from django.utils import timezone
from django.conf import settings
import time

logger = logging.getLogger('security')


class AdminIPAllowlistMiddleware:
    """
    If ADMIN_IP_ALLOWLIST is non-empty, restrict access to admin endpoints and
    custom admin-like paths to only those IPs. Otherwise, allow all.
    Targets:
      - /admin/
      - any path starting with /control/
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.allowlist = set(getattr(settings, 'ADMIN_IP_ALLOWLIST', []) or [])

    def __call__(self, request):
        # If no allowlist is configured, do nothing
        if not self.allowlist:
            return self.get_response(request)

        path = request.path or ''
        is_admin_path = path.startswith('/admin/') or path.startswith('/control/')
        if is_admin_path:
            ip = request.META.get('REMOTE_ADDR') or request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or 'unknown'
            if ip not in self.allowlist:
                logger.warning(f"Denied admin path access from IP {ip} to {path}")
                return HttpResponseForbidden('Access denied')
        return self.get_response(request)


class ActivityLoggingMiddleware:
    """Logs basic request/response info to the 'activity' logger."""
    def __init__(self, get_response):
        self.get_response = get_response
        self.log = logging.getLogger('activity')

    def __call__(self, request):
        start = time.time()
        user = getattr(request, 'user', None)
        ip = request.META.get('REMOTE_ADDR') or request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or ''
        ua = request.META.get('HTTP_USER_AGENT', '')[:200]
        method = request.method
        path = request.get_full_path()
        response = None
        try:
            response = self.get_response(request)
            return response
        finally:
            status = getattr(response, 'status_code', 0) if response is not None else 0
            duration_ms = int((time.time() - start) * 1000)
            uid = None
            uname = None
            if user and getattr(user, 'is_authenticated', False):
                uid = user.id
                uname = user.username
            msg = f"{timezone.now().isoformat()} method={method} path='{path}' status={status} ms={duration_ms} ip={ip} user_id={uid} user='{uname}' ua='{ua}'"
            try:
                self.log.info(msg)
            except Exception:
                pass
            # Persist to DB (best effort)
            try:
                from .models import RequestLog
                country = ''
                region = ''
                city = ''
                if ip:
                    c, r, ci = self._geo_lookup(ip)
                    country, region, city = c or '', r or '', ci or ''
                RequestLog.objects.create(
                    user=user if (user and getattr(user, 'is_authenticated', False)) else None,
                    method=method[:10],
                    path=path[:500],
                    status=int(status or 0),
                    duration_ms=int(duration_ms or 0),
                    ip=ip if ip else None,
                    user_agent=ua or '',
                    country=country[:64],
                    region=region[:128],
                    city=city[:128],
                )
            except Exception:
                # Never break request due to logging
                pass

    def _geo_lookup(self, ip: str):
        """Return (country, region, city) using GeoIP2 if configured; otherwise empty strings."""
        try:
            from django.contrib.gis.geoip2 import GeoIP2
            g = GeoIP2()
            city = g.city(ip)
            country_name = city.get('country_name') or ''
            region = city.get('region') or city.get('subdivisions', [{}])[0].get('names', {}).get('en', '') if isinstance(city.get('subdivisions'), list) else (city.get('region') or '')
            city_name = city.get('city') or ''
            return country_name, region, city_name
        except Exception:
            return '', '', ''
