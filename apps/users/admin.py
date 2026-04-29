from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import Profile
from apps.friends.models import Friend

# --- Inline dla Profilu ---
class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profil'
    fk_name = 'user'

# --- Inline dla Znajomych ---
class FriendInline(admin.TabularInline):
    model = Friend
    fk_name = 'user'
    raw_id_fields = ('friend',)
    extra = 0
    verbose_name = "Znajomy"
    verbose_name_plural = "Lista Znajomych (dodani przez tego użytkownika)"

    # Opcjonalnie: Uczynienie listy znajomych w panelu użytkownika tylko do odczytu
    # def has_add_permission(self, request, obj=None):
    #     return False

# --- Główny Admin Użytkownika ---
class CustomUserAdmin(UserAdmin):
    inlines = [ProfileInline, FriendInline]
    
    # Możemy rozszerzyć list_display o pola z profilu
    list_display = UserAdmin.list_display + ('get_city',)
    
    def get_city(self, obj):
        return obj.profile.city if hasattr(obj, 'profile') else '-'
    get_city.short_description = 'Miasto'
    
    get_city.short_description = 'Miasto'

    list_select_related = ('profile',) # Optymalizacja łączenia z profilem

# --- Rejestracja ---
# Najpierw wyrejestrowujemy domyślnego UserAdmina (lub tego z friends, jeśli jeszcze tam wisi w pamięci procesu)
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

admin.site.register(User, CustomUserAdmin)
