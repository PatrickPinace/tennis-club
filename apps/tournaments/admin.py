from django.contrib import admin
from .models import (
    Tournament, RoundRobinConfig, EliminationConfig, LadderConfig, AmericanoConfig, SwissSystemConfig,
    Participant, TeamMember, TournamentsMatch, ChallengeRejection, MatchScoreHistory, MatchReaction
)

# --- Inlines for Configs ---
class RoundRobinConfigInline(admin.StackedInline):
    model = RoundRobinConfig
    can_delete = False
    verbose_name_plural = "Konfiguracja Round Robin"

class EliminationConfigInline(admin.StackedInline):
    model = EliminationConfig
    can_delete = False
    verbose_name_plural = "Konfiguracja Eliminacji"

class LadderConfigInline(admin.StackedInline):
    model = LadderConfig
    can_delete = False
    verbose_name_plural = "Konfiguracja Drabinki"

class AmericanoConfigInline(admin.StackedInline):
    model = AmericanoConfig
    can_delete = False
    verbose_name_plural = "Konfiguracja Americano"

class SwissSystemConfigInline(admin.StackedInline):
    model = SwissSystemConfig
    can_delete = False
    verbose_name_plural = "Konfiguracja Systemu Szwajcarskiego"

# --- Inline for Participants ---
class ParticipantInline(admin.TabularInline):
    model = Participant
    extra = 1
    fields = ('display_name', 'user', 'status', 'seed_number')
    show_change_link = True

# --- Main Tournament Admin ---
@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'tournament_type', 'start_date', 'created_by')
    list_filter = ('status', 'tournament_type', 'facility')
    search_fields = ('name', 'description', 'created_by__username')
    inlines = [
        RoundRobinConfigInline,
        EliminationConfigInline,
        LadderConfigInline,
        AmericanoConfigInline,
        SwissSystemConfigInline,
        ParticipantInline
    ]
    actions = ['make_active', 'make_finished']

    def make_active(self, request, queryset):
        queryset.update(status=Tournament.Status.ACTIVE)
    make_active.short_description = "Zmień status na Aktywny"

    def make_finished(self, request, queryset):
        queryset.update(status=Tournament.Status.FINISHED)
    make_finished.short_description = "Zmień status na Zakończony"

# --- Matches Admin ---
@admin.register(TournamentsMatch)
class TournamentsMatchAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'tournament', 'status', 'winner', 'scheduled_time')
    list_filter = ('tournament', 'status', 'round_number')
    search_fields = ('tournament__name', 'participant1__display_name', 'participant2__display_name')
    list_select_related = ('tournament', 'participant1', 'participant2', 'winner')
    autocomplete_fields = ['participant1', 'participant2', 'winner']

# --- Participants Admin ---
@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'tournament', 'user', 'status', 'seed_number')
    list_filter = ('tournament', 'status')
    search_fields = ('display_name', 'user__username', 'tournament__name')
    list_select_related = ('tournament', 'user')

# --- Other Admins ---
@admin.register(MatchScoreHistory)
class MatchScoreHistoryAdmin(admin.ModelAdmin):
    list_display = ('match', 'updated_by', 'updated_at')
    readonly_fields = ('match', 'updated_by', 'updated_at', 'set1_p1_score', 'set1_p2_score', 'set2_p1_score', 'set2_p2_score', 'set3_p1_score', 'set3_p2_score')

    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False

@admin.register(ChallengeRejection)
class ChallengeRejectionAdmin(admin.ModelAdmin):
    list_display = ('tournament', 'rejecting_participant', 'challenger_participant', 'created_at')

@admin.register(MatchReaction)
class MatchReactionAdmin(admin.ModelAdmin):
    list_display = ('match', 'user', 'emoji', 'created_at')
