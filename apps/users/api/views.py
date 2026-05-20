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

        # Tryb podpowiedzi — kilka ostatnich userów bez filtrowania
        if self.request.query_params.get('suggest') == '1':
            return User.objects.order_by('-date_joined')[:8]

        q = self.request.query_params.get('search', '').strip()
        if len(q) < 2:
            return User.objects.none()
        return (
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
            .order_by('relevance', 'last_name', 'first_name')[:20]
        )


class UserDetailsView(APIView):
    """Returns details of the currently logged-in user."""
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        serializer = UserDetailsSerializer(request.user)
        return Response(serializer.data)
