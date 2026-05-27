from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth.models import User
from apps.users.api.serializers import RegisterSerializer, UserDetailsSerializer

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = RegisterSerializer


class UserListView(generics.ListAPIView):
    """
    Lista użytkowników z filtrowaniem po ?search= i trybem podpowiedzi ?suggest=1.

    ?search=<query> — filtruje po first_name, last_name, username (icontains, OR).
      Bez search lub query < 2 znaki → pusta lista (nie ujawniamy wszystkich).
      Wyniki posortowane relevance-first, limit 20.

    ?suggest=1 — zwraca do 8 ostatnio zarejestrowanych użytkowników (bez filtrowania).
      Używane przez autocomplete jako "startowe sugestie" przy focus na polu search.
    """
    serializer_class = UserDetailsSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        from django.db.models import Q, Case, When, IntegerField
        from apps.tournaments.models import Participant, TeamMember

        # Opcjonalne wykluczenie już dodanych uczestników turnieju
        exclude_tournament = self.request.query_params.get('exclude_tournament', '').strip()
        excluded_user_ids = set()
        if exclude_tournament.isdigit():
            tid = int(exclude_tournament)
            # Kapitanowie / singliści — bezpośrednio w Participant.user
            captain_ids = set(
                Participant.objects
                .filter(tournament_id=tid)
                .exclude(user_id=None)
                .values_list('user_id', flat=True)
            )
            # Partnerzy w deblach — przechowywani w TeamMember
            partner_ids = set(
                TeamMember.objects
                .filter(participant__tournament_id=tid)
                .exclude(user_id=None)
                .values_list('user_id', flat=True)
            )
            excluded_user_ids = captain_ids | partner_ids

        # Tryb podpowiedzi — kilka ostatnich userów bez filtrowania
        if self.request.query_params.get('suggest') == '1':
            qs = User.objects.order_by('-date_joined')
            if excluded_user_ids:
                qs = qs.exclude(id__in=excluded_user_ids)
            return qs[:8]

        q = self.request.query_params.get('search', '').strip()
        if len(q) < 2:
            return User.objects.none()
        qs = (
            User.objects
            .filter(
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q) |
                Q(username__icontains=q)
            )
            .annotate(
                relevance=Case(
                    When(username__iexact=q, then=0),
                    When(username__istartswith=q, then=1),
                    When(first_name__istartswith=q, then=2),
                    When(last_name__istartswith=q, then=2),
                    default=3,
                    output_field=IntegerField(),
                )
            )
            .order_by('relevance', 'last_name', 'first_name')
        )
        if excluded_user_ids:
            qs = qs.exclude(id__in=excluded_user_ids)
        return qs[:20]


class UserDetailsView(APIView):
    """Returns details of the currently logged-in user."""
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        serializer = UserDetailsSerializer(request.user)
        return Response(serializer.data)
