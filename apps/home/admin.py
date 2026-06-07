import datetime
from django.contrib import admin
from django.utils import timezone
from .models import BlockedPattern, LoginAttempt, PageView

@admin.register(BlockedPattern)
class BlockedPatternAdmin(admin.ModelAdmin):
    list_display = ('pattern', 'is_active', 'created_at', 'description')
    list_filter = ('is_active', 'created_at')
    search_fields = ('pattern', 'description')
    list_editable = ('is_active',)





@admin.register(PageView)
class PageViewAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "path", "ip_address", "method", "browser_device", "user")
    list_filter = ("method", "timestamp")
    search_fields = ("path", "ip_address", "user_agent")
    date_hierarchy = "timestamp"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.exclude(ip_address='51.83.160.216')

    @admin.display(description="Przeglądarka / Urządzenie")
    def browser_device(self, obj):
        return f"{obj.browser} ({obj.device})"

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}

        # Copy GET parameters and pop custom 'stats_days' to prevent Django Admin from treating it as a database lookup
        request.GET = request.GET.copy()
        stats_days = request.GET.pop('stats_days', ['7'])
        if isinstance(stats_days, list):
            stats_days = stats_days[0] if stats_days else '7'
        if stats_days not in ['1', '7', '30', 'all']:
            stats_days = '7'

        now = timezone.now()
        start_date = None
        if stats_days == '1':
            start_date = now - datetime.timedelta(days=1)
        elif stats_days == '7':
            start_date = now - datetime.timedelta(days=7)
        elif stats_days == '30':
            start_date = now - datetime.timedelta(days=30)

        # Base queryset for stats
        qs = self.get_queryset(request)
        if start_date:
            qs = qs.filter(timestamp__gte=start_date)

        # General stats
        total_views = qs.count()
        unique_visitors = qs.values('ip_address').distinct().count()
        unique_sessions = qs.values('session_key').distinct().count()

        # Top 10 pages
        from django.db.models import Count, Max
        top_pages_qs = qs.values('path').annotate(
            total=Count('id'),
            unique=Count('ip_address', distinct=True)
        ).order_by('-total')[:10]

        top_pages = []
        for p in top_pages_qs:
            top_pages.append({
                'path': p['path'],
                'total': p['total'],
                'unique': p['unique']
            })

        # Top 10 visitors
        top_visitors_qs = qs.values('ip_address').annotate(
            total=Count('id'),
            last_visit=Max('timestamp')
        ).order_by('-total')[:10]

        top_visitors = []
        for v in top_visitors_qs:
            ip = v['ip_address']
            latest_pv = qs.filter(ip_address=ip).order_by('-timestamp').first()
            browser = latest_pv.browser if latest_pv else 'Inny'
            device = latest_pv.device if latest_pv else 'Desktop'
            user_agent = latest_pv.user_agent if latest_pv else ''

            top_visitors.append({
                'ip_address': ip or 'Nieznany',
                'total': v['total'],
                'last_visit': v['last_visit'],
                'browser': browser,
                'device': device,
                'user_agent': user_agent
            })

        # Generate chart data
        chart_data = []
        if stats_days == '1':
            for i in range(24):
                dt = now - datetime.timedelta(hours=23 - i)
                hour_start = dt.replace(minute=0, second=0, microsecond=0)
                hour_end = hour_start + datetime.timedelta(hours=1)

                views_count = qs.filter(timestamp__gte=hour_start, timestamp__lt=hour_end).count()
                visitors_count = qs.filter(timestamp__gte=hour_start, timestamp__lt=hour_end).values('ip_address').distinct().count()

                chart_data.append({
                    'date': hour_start.strftime('%H:%M'),
                    'views': views_count,
                    'visitors': visitors_count
                })
        else:
            days_count = 7 if stats_days == '7' else (30 if stats_days == '30' else 90)
            if stats_days == 'all':
                earliest = qs.order_by('timestamp').first()
                if earliest:
                    delta = now - earliest.timestamp
                    days_count = min(max(delta.days + 1, 7), 180)
                else:
                    days_count = 30

            for i in range(days_count):
                dt = now - datetime.timedelta(days=days_count - 1 - i)
                day_start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
                day_end = day_start + datetime.timedelta(days=1)

                views_count = qs.filter(timestamp__gte=day_start, timestamp__lt=day_end).count()
                visitors_count = qs.filter(timestamp__gte=day_start, timestamp__lt=day_end).values('ip_address').distinct().count()

                chart_data.append({
                    'date': day_start.strftime('%d.%m'),
                    'views': views_count,
                    'visitors': visitors_count
                })

        # Build filter URLs
        base_url = request.path
        def get_filter_url(days):
            params = request.GET.copy()
            params['stats_days'] = days
            return f"{base_url}?{params.urlencode()}"

        filter_urls = {
            '1': get_filter_url('1'),
            '7': get_filter_url('7'),
            '30': get_filter_url('30'),
            'all': get_filter_url('all'),
        }

        extra_context.update({
            'stats_days': stats_days,
            'total_views': total_views,
            'unique_visitors': unique_visitors,
            'unique_sessions': unique_sessions,
            'top_pages': top_pages,
            'top_visitors': top_visitors,
            'chart_data': chart_data,
            'filter_urls': filter_urls,
        })

        return super().changelist_view(request, extra_context=extra_context)


