from django.contrib import admin
from .models import TennisFacility, Court, Reservation

class CourtInline(admin.TabularInline):
    model = Court
    extra = 1

@admin.register(TennisFacility)
class TennisFacilityAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'surface', 'reservation')
    search_fields = ('name', 'address')
    inlines = [CourtInline]

@admin.register(Court)
class CourtAdmin(admin.ModelAdmin):
    list_display = ('facility', 'court_number', 'surface', 'is_indoor')
    list_filter = ('facility', 'surface', 'is_indoor')

@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ('court', 'user', 'start_time', 'end_time', 'status')
    list_filter = ('status', 'court__facility', 'start_time')
    search_fields = ('user__username', 'court__facility__name')
