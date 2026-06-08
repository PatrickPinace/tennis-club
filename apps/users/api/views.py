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
            # Kapitanowie / singliści — tylko aktywni (nie WDN — można ich ponownie dodać)
            captain_ids = set(
                Participant.objects
                .filter(tournament_id=tid)
                .exclude(user_id=None)
                .exclude(status='WDN')
                .values_list('user_id', flat=True)
            )
            # Partnerzy w deblach — tylko aktywni
            partner_ids = set(
                TeamMember.objects
                .filter(participant__tournament_id=tid)
                .exclude(user_id=None)
                .exclude(participant__status='WDN')
                .values_list('user_id', flat=True)
            )
            excluded_user_ids = captain_ids | partner_ids

        # Tryb podpowiedzi — kilka ostatnich userów bez filtrowania
        if self.request.query_params.get('suggest') == '1':
            qs = User.objects.order_by('-date_joined')
            if excluded_user_ids:
                qs = qs.exclude(id__in=excluded_user_ids)
            return qs[:8]

        import unicodedata

        _PL_MAP = str.maketrans('ąćęłńóśźżĄĆĘŁŃÓŚŹŻ', 'acelnoszzACELNOSZZ')

        def normalize(s: str) -> str:
            """Usuń akcenty (w tym polskie znaki) i zamień na małe litery."""
            s = s.translate(_PL_MAP)
            return ''.join(
                c for c in unicodedata.normalize('NFD', s.lower())
                if unicodedata.category(c) != 'Mn'
            )

        q = self.request.query_params.get('search', '').strip()
        if len(q) < 2:
            return User.objects.none()

        # Rozbij zapytanie na tokeny — "paweł s" → ["pawel", "s"]
        tokens = normalize(q).split()

        # Pobierz wszystkich kandydatów i filtruj w Pythonie z normalizacją
        # (obsługuje polskie znaki i wielotokenowe zapytania niezależnie od bazy)
        candidates = User.objects.all()
        if excluded_user_ids:
            candidates = candidates.exclude(id__in=excluded_user_ids)

        # Filtruj w Pythonie: normalizuj i sprawdź wszystkie tokeny
        matched_ids = []
        for u in candidates.values('id', 'first_name', 'last_name', 'username'):
            full = normalize(f"{u['first_name']} {u['last_name']} {u['username']}")
            if all(t in full for t in tokens):
                matched_ids.append(u['id'])

        # Typo-tolerant fallback — uruchamia się tylko gdy exact/partial zwróciło 0 wyników.
        # Porównuje znormalizowane tokeny zapytania do słów imienia i nazwiska użytkownika
        # przez trigram similarity. Próg 0.3 — warto zweryfikować na realnych danych.
        fuzzy_scores: dict[int, float] = {}
        if not matched_ids:
            def trigram_sim(a: str, b: str) -> float:
                if len(a) < 2 or len(b) < 2:
                    return 1.0 if a == b else 0.0
                def trigrams(s: str):
                    s = f'  {s} '
                    return {s[i:i+3] for i in range(len(s) - 2)}
                ta, tb = trigrams(a), trigrams(b)
                return len(ta & tb) / len(ta | tb) if ta | tb else 0.0

            FUZZY_THRESHOLD = 0.3
            fuzzy_tokens = [t for t in tokens if len(t) >= 4]
            if fuzzy_tokens:
                for u in candidates.values('id', 'first_name', 'last_name'):
                    name_words = normalize(f"{u['first_name']} {u['last_name']}").split()
                    # Każdy kwalifikujący token musi mieć przynajmniej jedno słowo z nazwy powyżej progu
                    token_scores = [
                        max((trigram_sim(t, w) for w in name_words), default=0.0)
                        for t in fuzzy_tokens
                    ]
                    if all(s >= FUZZY_THRESHOLD for s in token_scores):
                        uid = u['id']
                        # Uwzględnij też krótkie tokeny jako partial bonus do score
                        short_bonus = sum(
                            0.5 for t in tokens if len(t) < 4 and len(t) >= 2
                            and any(t in w for w in name_words)
                        )
                        fuzzy_scores[uid] = sum(token_scores) + short_bonus
                        matched_ids.append(uid)

        if not matched_ids:
            return User.objects.none()

        if fuzzy_scores:
            # Fuzzy: sortuj po podobieństwie malejąco, exact relevance nie ma tu sensu
            sorted_ids = sorted(matched_ids, key=lambda uid: fuzzy_scores.get(uid, 0), reverse=True)
            id_order = {uid: i for i, uid in enumerate(sorted_ids)}
            return sorted(
                User.objects.filter(id__in=matched_ids),
                key=lambda u: id_order.get(u.id, 99)
            )[:20]

        qs = (
            User.objects
            .filter(id__in=matched_ids)
            .annotate(
                relevance=Case(
                    When(username__iexact=q, then=0),
                    When(username__istartswith=q, then=1),
                    When(first_name__istartswith=tokens[0], then=2),
                    When(last_name__istartswith=tokens[0], then=2),
                    default=3,
                    output_field=IntegerField(),
                )
            )
            .order_by('relevance', 'last_name', 'first_name')
        )
        return qs[:20]


class UserDetailsView(APIView):
    """Returns details of the currently logged-in user."""
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        serializer = UserDetailsSerializer(request.user)
        return Response(serializer.data)
