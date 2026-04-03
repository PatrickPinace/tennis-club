from django.contrib import admin
from .models import BlockedPattern

@admin.register(BlockedPattern)
class BlockedPatternAdmin(admin.ModelAdmin):
    list_display = ('pattern', 'is_active', 'created_at', 'description')
    list_filter = ('is_active', 'created_at')
    search_fields = ('pattern', 'description')
    list_editable = ('is_active',)
