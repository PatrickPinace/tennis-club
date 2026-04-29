from django.contrib import admin
from django.utils.html import format_html
from .models import Match

@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ("match_date", "description", "get_players_display", "score_display", "match_double")
    list_filter = ("match_double", "match_date")
    search_fields = ("description", "p1__username", "p2__username", "p3__username", "p4__username")
    ordering = ("-match_date",)
    list_select_related = ("p1", "p2", "p3", "p4")
    raw_id_fields = ("p1", "p2", "p3", "p4")

    fieldsets = (
        ("Informacje ogólne", {
            "fields": ("match_date", "description", "match_double")
        }),
        ("Wynik", {
            "fields": (
                ("p1_set1", "p2_set1"),
                ("p1_set2", "p2_set2"),
                ("p1_set3", "p2_set3"),
            ),
            "description": "Wpisz wynik dla każdego seta. Pozostaw puste dla nierozegranych setów."
        }),
        ("Gracze", {
            "fields": ("p1", "p2", "p3", "p4")
        }),
    )

    def get_players_display(self, obj):
        if obj.match_double:
            team1 = f"{obj.p1} & {obj.p3}" if obj.p3 else f"{obj.p1} & (Brak)"
            team2 = f"{obj.p2} & {obj.p4}" if obj.p4 else f"{obj.p2} & (Brak)"
            return f"{team1} vs {team2}"
        else:
            return f"{obj.p1} vs {obj.p2}"
    get_players_display.short_description = "Gracze / Drużyny"

    def score_display(self, obj):
        sets = []
        if obj.p1_set1 is not None and obj.p2_set1 is not None:
            sets.append(f"{obj.p1_set1}:{obj.p2_set1}")
        if obj.p1_set2 is not None and obj.p2_set2 is not None:
            sets.append(f"{obj.p1_set2}:{obj.p2_set2}")
        if obj.p1_set3 is not None and obj.p2_set3 is not None:
            sets.append(f"{obj.p1_set3}:{obj.p2_set3}")
        
        score_str = ", ".join(sets)
        return format_html("<b>{}</b>", score_str) if score_str else "-"
    score_display.short_description = "Wynik"
