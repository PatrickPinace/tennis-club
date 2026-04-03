from django.contrib import admin
from .models import Activity, TennisData

class TennisDataInline(admin.StackedInline):
    model = TennisData
    can_delete = False
    verbose_name_plural = 'Tennis Data'

@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ('activity_id', 'user', 'activity_name', 'start_time', 'duration_in_minutes', 'tennis_data_fetched')
    list_filter = ('tennis_data_fetched', 'start_time', 'activity_type_key')
    search_fields = ('user__username', 'activity_name', 'activity_id')
    inlines = [TennisDataInline]
