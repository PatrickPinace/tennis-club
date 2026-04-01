"""Django Admin configuration for Tennis Club v2."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import (
    Profile,
    Facility, Court, Reservation,
    Match,
    Tournament, TournamentConfig, Participant, TournamentMatch,
    TournamentManager, TournamentEventLog,
    RankingHistory, TournamentRankPoints,
    Notification,
    Friendship, FriendRequest,
)


# ====================
# Inline Admin Classes
# ====================

class ProfileInline(admin.StackedInline):
    """Inline profile for User admin."""
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'


class CourtInline(admin.TabularInline):
    """Inline courts for Facility admin."""
    model = Court
    extra = 1


class TournamentConfigInline(admin.StackedInline):
    """Inline config for Tournament admin."""
    model = TournamentConfig
    can_delete = False


# ====================
# Custom User Admin
# ====================

class UserAdmin(BaseUserAdmin):
    """Extended User admin with Profile inline."""
    inlines = [ProfileInline]


# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


# ====================
# Profile Admin
# ====================

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'city', 'elo_rating', 'ranking_points', 'created_at']
    list_filter = ['city', 'created_at']
    search_fields = ['user__username', 'user__email', 'city']
    ordering = ['-elo_rating']
    readonly_fields = ['created_at']


# ====================
# Facilities & Courts
# ====================

@admin.register(Facility)
class FacilityAdmin(admin.ModelAdmin):
    list_display = ['name', 'address', 'owner', 'default_surface', 'is_active', 'created_at']
    list_filter = ['default_surface', 'is_active', 'created_at']
    search_fields = ['name', 'address', 'owner__username']
    inlines = [CourtInline]
    readonly_fields = ['created_at']


@admin.register(Court)
class CourtAdmin(admin.ModelAdmin):
    list_display = ['facility', 'number', 'surface', 'is_indoor', 'is_active']
    list_filter = ['facility', 'surface', 'is_indoor', 'is_active']
    search_fields = ['facility__name']
    ordering = ['facility', 'number']


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ['court', 'user', 'start_time', 'end_time', 'status', 'created_at']
    list_filter = ['status', 'created_at', 'court__facility']
    search_fields = ['user__username', 'court__facility__name']
    date_hierarchy = 'start_time'
    readonly_fields = ['created_at', 'updated_at']


# ====================
# Matches
# ====================

@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ['match_date', 'player1', 'player2', 'is_doubles', 'winner_side', 'court']
    list_filter = ['is_doubles', 'match_date', 'court__facility']
    search_fields = ['player1__username', 'player2__username', 'description']
    date_hierarchy = 'match_date'
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Podstawowe informacje', {
            'fields': ('match_date', 'description', 'is_doubles', 'court')
        }),
        ('Gracze', {
            'fields': ('player1', 'player2', 'player3', 'player4')
        }),
        ('Wyniki', {
            'fields': (
                ('set1_p1', 'set1_p2'),
                ('set2_p1', 'set2_p2'),
                ('set3_p1', 'set3_p2'),
                'winner_side'
            )
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


# ====================
# Tournaments
# ====================

@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = ['name', 'tournament_type', 'match_format', 'start_date', 'status', 'visibility', 'rank']
    list_filter = ['status', 'tournament_type', 'match_format', 'visibility', 'registration_mode', 'rank', 'start_date']
    search_fields = ['name', 'description']
    date_hierarchy = 'start_date'
    inlines = [TournamentConfigInline]
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Podstawowe informacje', {
            'fields': ('name', 'description', 'facility')
        }),
        ('Typ i format', {
            'fields': ('tournament_type', 'match_format', 'rank')
        }),
        ('Widoczność i rejestracja', {
            'fields': ('visibility', 'registration_mode', 'min_participants', 'max_participants')
        }),
        ('Daty rejestracji', {
            'fields': ('registration_open_at', 'registration_deadline')
        }),
        ('Daty turnieju', {
            'fields': ('start_date', 'end_date', 'finished_at', 'cancelled_at')
        }),
        ('Status', {
            'fields': ('status', 'winner')
        }),
        ('Metadata', {
            'fields': ('created_by', 'updated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'tournament', 'user', 'seed', 'status', 'final_position', 'points', 'matches_won']
    list_filter = ['tournament', 'status']
    search_fields = ['user__username', 'display_name', 'tournament__name']
    readonly_fields = ['joined_at', 'created_at']
    fieldsets = (
        ('Uczestnik', {
            'fields': ('tournament', 'user', 'partner', 'display_name', 'seed', 'status')
        }),
        ('Lifecycle tracking', {
            'fields': ('joined_at', 'approved_at', 'withdrawn_at', 'withdrawal_reason', 'final_position'),
            'classes': ('collapse',)
        }),
        ('Statystyki (Round Robin)', {
            'fields': (
                'points',
                ('matches_won', 'matches_lost'),
                ('sets_won', 'sets_lost'),
                ('games_won', 'games_lost')
            )
        }),
    )


@admin.register(TournamentMatch)
class TournamentMatchAdmin(admin.ModelAdmin):
    list_display = ['tournament', 'round_number', 'match_number', 'player1_participant', 'player2_participant', 'status', 'winner_participant']
    list_filter = ['tournament', 'status', 'round_number']
    search_fields = ['tournament__name', 'player1_participant__display_name', 'player2_participant__display_name']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Mecz', {
            'fields': ('tournament', 'round_number', 'match_number', 'bracket_position', 'status', 'court')
        }),
        ('Uczestnicy', {
            'fields': ('player1_participant', 'player2_participant')
        }),
        ('Struktura drabinki', {
            'fields': ('source_match_1', 'source_match_2'),
            'classes': ('collapse',)
        }),
        ('Wyniki', {
            'fields': (
                ('set1_p1', 'set1_p2'),
                ('set2_p1', 'set2_p2'),
                ('set3_p1', 'set3_p2'),
                'winner_participant',
                'loser_participant',
                'walkover_reason'
            )
        }),
        ('Harmonogram', {
            'fields': ('scheduled_time', 'completed_at')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(TournamentManager)
class TournamentManagerAdmin(admin.ModelAdmin):
    list_display = ['tournament', 'user', 'role', 'created_at']
    list_filter = ['tournament', 'role', 'created_at']
    search_fields = ['tournament__name', 'user__username']
    readonly_fields = ['created_at']
    fieldsets = (
        ('Manager', {
            'fields': ('tournament', 'user', 'role')
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(TournamentEventLog)
class TournamentEventLogAdmin(admin.ModelAdmin):
    list_display = ['tournament', 'event_type', 'actor', 'created_at']
    list_filter = ['event_type', 'tournament', 'created_at']
    search_fields = ['tournament__name', 'actor__username']
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at']
    fieldsets = (
        ('Zdarzenie', {
            'fields': ('tournament', 'event_type', 'actor', 'payload')
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


# ====================
# Rankings
# ====================

@admin.register(RankingHistory)
class RankingHistoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'date', 'position', 'elo_rating', 'ranking_points', 'wins', 'losses']
    list_filter = ['date']
    search_fields = ['user__username']
    date_hierarchy = 'date'
    ordering = ['date', 'position']


@admin.register(TournamentRankPoints)
class TournamentRankPointsAdmin(admin.ModelAdmin):
    list_display = ['rank', 'winner_points', 'finalist_points', 'semifinal_points', 'quarterfinal_points', 'participation_points']
    ordering = ['rank']


# ====================
# Notifications
# ====================

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'notification_type', 'title', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['user__username', 'title', 'message']
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at']


# ====================
# Friends
# ====================

@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    list_display = ['user', 'friend', 'created_at']
    search_fields = ['user__username', 'friend__username']
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at']


@admin.register(FriendRequest)
class FriendRequestAdmin(admin.ModelAdmin):
    list_display = ['sender', 'receiver', 'status', 'created_at', 'updated_at']
    list_filter = ['status', 'created_at']
    search_fields = ['sender__username', 'receiver__username']
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at', 'updated_at']
