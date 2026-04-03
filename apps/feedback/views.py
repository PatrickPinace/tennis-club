from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .forms import FeedbackForm
from django.views.generic import ListView
from django.views import View
from django.contrib.auth.mixins import UserPassesTestMixin
from .models import Feedback
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
User = get_user_model()

def get_client_ip(request):
    """Pobiera adres IP klienta z żądania."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


@require_POST
def submit_feedback(request):
    form = FeedbackForm(request.POST)
    if form.is_valid():
        feedback = form.save(commit=False)
        feedback.ip_address = get_client_ip(request)  # Pobranie i zapisanie IP
        if request.user.is_authenticated:
            feedback.user = request.user
        feedback.save()
        return JsonResponse({'success': True, 'message': 'Dziękujemy za Twoje zgłoszenie! Postaramy się je jak najszybciej przeanalizować.'})
    else:
        # Konwertuj błędy formularza na string, aby można je było łatwo wyświetlić
        errors = {field: error[0] for field, error in form.errors.items()}
        return JsonResponse({
            'success': False, 
            'errors': errors,
            'message': 'Formularz zawiera błędy. Prosimy, popraw je i spróbuj ponownie.'
        }, status=400)

class UpdateFeedbackStatusView(View):
    """
    Widok do aktualizacji statusu zgłoszenia przez administratora.
    """
    def post(self, request, feedback_id):
        # Sprawdzenie uprawnień
        if not request.user.is_authenticated or request.user.username != 'lmoryl':
            return JsonResponse({'status': 'error', 'message': 'Brak uprawnień.'}, status=403)

        feedback = get_object_or_404(Feedback, id=feedback_id)
        new_status = request.POST.get('status')

        if new_status not in Feedback.Status.values:
            return JsonResponse({'status': 'error', 'message': 'Nieprawidłowy status.'}, status=400)

        feedback.status = new_status
        feedback.save()

        return JsonResponse({
            'status': 'success',
            'message': f'Status zgłoszenia został zaktualizowany na "{feedback.get_status_display()}".'
        })

class FeedbackListView(UserPassesTestMixin, ListView):
    """
    Widok listy zgłoszeń, dostępny tylko dla administratora.
    """
    model = Feedback
    template_name = 'feedback/feedback_list.html'
    context_object_name = 'feedback_list'
    paginate_by = 25

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.username == 'lmoryl'

    def get_queryset(self):
        return Feedback.objects.all().select_related('user').order_by('status', '-created_at')