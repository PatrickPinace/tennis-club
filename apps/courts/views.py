from datetime import datetime, date, timedelta
from django.urls import reverse_lazy, reverse
from django.http import HttpResponseBadRequest, JsonResponse
from django.views.generic import ListView, DetailView, CreateView, UpdateView, View, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, HttpResponseRedirect
from django.core.exceptions import PermissionDenied
from .models import TennisFacility, Court, Reservation
from .forms import ReservationForm, TennisFacilityForm, CourtForm
from notifications.views import notify_user
from collections import defaultdict


class FacilityListView(ListView):
    model = TennisFacility
    template_name = 'courts/facility_list.html'
    context_object_name = 'facilities'


class FacilityDetailView(DetailView):
    model = TennisFacility
    template_name = 'courts/facility_detail.html'
    context_object_name = 'facility'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        selected_date_str = self.request.GET.get('date', date.today().isoformat())
        try:
            selected_date = date.fromisoformat(selected_date_str)
        except (ValueError, TypeError):
            selected_date = date.today()

        time_slots = [f"{h:02d}:{m:02d}" for h in range(6, 23) for m in (0, 30)]
        context['time_slots'] = time_slots
        context['selected_date'] = selected_date
        context['next_seven_days'] = [date.today() + timedelta(days=i) for i in range(7)]
        context['is_owner'] = self.request.user == self.object.owner
        
        # Dodaj aktualną godzinę, jeśli oglądamy dzisiejszy dzień
        if selected_date == date.today():
            context['current_time_str'] = datetime.now().strftime('%H:%M')

        # Pobieranie i sortowanie turniejów
        all_tournaments = self.object.tournaments.all().order_by('-end_date')
        displayable_tournaments = all_tournaments.filter(
            status__in=['REG', 'SCH', 'ACT', 'FIN']
        )
        context['displayable_tournaments'] = displayable_tournaments
        return context


class TimelineDataView(View):
    """Zwraca dane JSON dla osi czasu dla danego obiektu i daty."""
    def get(self, request, pk):
        facility = get_object_or_404(TennisFacility, pk=pk)
        selected_date_str = request.GET.get('date', date.today().isoformat())
        selected_date = date.fromisoformat(selected_date_str)
        user = request.user

        courts_list = Court.objects.filter(facility=facility)
        courts_data = []

        for court in courts_list:
            reservations = court.reservations.filter(
                start_time__date=selected_date
            ).select_related('user').exclude(status__in=['REJECTED', 'CHANGED'])

            timeline_slots_details = {}
            for res in reservations:
                current_time = res.start_time
                while current_time < res.end_time:
                    slot_time_str = current_time.strftime('%H:%M')
                    is_current_user = user.is_authenticated and res.user_id == user.id
                    timeline_slots_details[slot_time_str] = {
                        'status': res.status,
                        'status_display': res.get_status_display(),
                        'is_current_user': is_current_user,
                        'reservation_id': res.id,
                        'user_full_name': res.user.get_full_name(),
                        'start_time': res.start_time.strftime('%H:%M'),
                        'end_time': res.end_time.strftime('%H:%M')
                    }
                    current_time += timedelta(minutes=30)
            
            courts_data.append({
                'id': court.id,
                'court_number': court.court_number,
                'timeline_slots': timeline_slots_details,
            })

        return JsonResponse({'courts_data': courts_data})


class CreateReservationView(LoginRequiredMixin, CreateView):
    model = Reservation
    form_class = ReservationForm
    template_name = 'courts/reservation_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.facility = None
        # Usunięto logikę edycji, ten widok teraz tylko tworzy
        facility_id = self.request.GET.get('facility_id') or self.request.POST.get('facility_id')
        if facility_id:
            self.facility = get_object_or_404(TennisFacility, pk=facility_id)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.facility:
           kwargs['facility'] = self.facility
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        initial['reservation_date'] = self.request.GET.get('date', date.today())
        initial['start_time'] = self.request.GET.get('start_time', '12:00')
        return initial

    def post(self, request, *args, **kwargs):
        """
        Obsługuje trzy rodzaje żądań POST:
        1. Z osi czasu przez zwykłego użytkownika (zawiera 'selected_slots'): przetwarza sloty i renderuje formularz podsumowania.
        2. Z osi czasu przez właściciela (zawiera 'selected_slots' i 'confirm_as_owner'): tworzy zatwierdzone rezerwacje.
        3. Z formularza podsumowania (zawiera 'confirm_reservations'): tworzy rezerwacje oczekujące.
        """
        if 'selected_slots' in request.POST:
            if 'confirm_as_owner' in request.POST:
                # Krok 1b: Właściciel tworzy zatwierdzone rezerwacje od razu
                return self.handle_owner_reservation_post(request)
            else:
                # Krok 1a: Zwykły użytkownik idzie do podsumowania
                return self.handle_timeline_post(request)
        elif 'confirm_reservations' in request.POST:
            # Krok 2: Zwykły użytkownik tworzy rezerwacje po potwierdzeniu
            return self.handle_confirmation_post(request)
        
        return HttpResponseBadRequest("Nieprawidłowe żądanie.")

    def handle_timeline_post(self, request):
        selected_slots_str = request.POST.get('selected_slots')
        if not selected_slots_str:
            return HttpResponseBadRequest("Nie wybrano żadnych godzin.")

        import json
        try:
            selected_slots = json.loads(selected_slots_str)
        except json.JSONDecodeError:
            return HttpResponseBadRequest("Błędny format danych.")

        if not selected_slots:
            return HttpResponseBadRequest("Nie wybrano żadnych godzin.")

        reservations_to_create = []
        for court_id, slots in selected_slots.items():
            if not slots: continue
            court = get_object_or_404(Court, pk=court_id)
            slots.sort()
            
            start_slot = slots[0]
            end_slot_time = datetime.strptime(start_slot, '%H:%M').time()

            for i in range(1, len(slots)):
                current_slot_time = datetime.strptime(slots[i], '%H:%M').time()
                expected_next_time = (datetime.combine(date.today(), end_slot_time) + timedelta(minutes=30)).time()

                if current_slot_time == expected_next_time:
                    end_slot_time = current_slot_time
                else:
                    reservations_to_create.append({'court': court, 'start_time': datetime.strptime(start_slot, '%H:%M').time(), 'end_time': (datetime.combine(date.today(), end_slot_time) + timedelta(minutes=30)).time()})
                    start_slot = slots[i]
                    end_slot_time = datetime.strptime(start_slot, '%H:%M').time()
            
            reservations_to_create.append({'court': court, 'start_time': datetime.strptime(start_slot, '%H:%M').time(), 'end_time': (datetime.combine(date.today(), end_slot_time) + timedelta(minutes=30)).time()})

        # Ustawiamy facility na podstawie pierwszego kortu
        self.facility = reservations_to_create[0]['court'].facility if reservations_to_create else None

        # Ręczne ustawienie self.object na None, aby spełnić wymagania nadrzędnego get_context_data
        self.object = None

        context = self.get_context_data(
            reservations_to_create=reservations_to_create,
            reservation_date=datetime.strptime(request.POST.get('selected_date'), '%Y-%m-%d').date()
        )
        return self.render_to_response(context)

    def handle_owner_reservation_post(self, request):
        selected_slots_str = request.POST.get('selected_slots')
        if not selected_slots_str:
            return JsonResponse({'success': False, 'error': 'Nie wybrano żadnych godzin.'}, status=400)

        import json
        try:
            selected_slots = json.loads(selected_slots_str)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Błędny format danych.'}, status=400)

        if not selected_slots:
            return JsonResponse({'success': False, 'error': 'Nie wybrano żadnych godzin.'}, status=400)

        reservation_date = datetime.strptime(request.POST.get('selected_date'), '%Y-%m-%d').date()
        
        for court_id, slots in selected_slots.items():
            if not slots: continue
            court = get_object_or_404(Court, pk=court_id)

            # Sprawdzenie uprawnień - czy użytkownik jest właścicielem tego kortu
            if court.facility.owner != request.user:
                return JsonResponse({'success': False, 'error': 'Brak uprawnień.'}, status=403)

            slots.sort()
            
            start_slot = slots[0]
            end_slot_time = datetime.strptime(start_slot, '%H:%M').time()

            for i in range(1, len(slots)):
                current_slot_time = datetime.strptime(slots[i], '%H:%M').time()
                expected_next_time = (datetime.combine(date.today(), end_slot_time) + timedelta(minutes=30)).time()

                if current_slot_time == expected_next_time:
                    end_slot_time = current_slot_time
                else:
                    self.create_confirmed_reservation(request.user, court, reservation_date, datetime.strptime(start_slot, '%H:%M').time(), (datetime.combine(date.today(), end_slot_time) + timedelta(minutes=30)).time())
                    start_slot = slots[i]
                    end_slot_time = datetime.strptime(start_slot, '%H:%M').time()
            
            self.create_confirmed_reservation(request.user, court, reservation_date, datetime.strptime(start_slot, '%H:%M').time(), (datetime.combine(date.today(), end_slot_time) + timedelta(minutes=30)).time())

        return JsonResponse({'success': True})

    def handle_confirmation_post(self, request):
        # Ta metoda jest teraz odpowiednikiem starej `form_valid`
        self.request = request
        # Pobranie facility_id z ukrytego pola w formularzu
        facility_id = request.POST.get('facility_id')
        if facility_id:
            self.facility = get_object_or_404(TennisFacility, pk=facility_id)
        
        # Zmieniamy odpowiedź na JSON dla zapytań AJAX
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        form = self.get_form() # Używamy pustego formularza, bo dane są w POST
        if self.form_valid(form, is_ajax=is_ajax):
            if is_ajax:
                return JsonResponse({'success': True, 'redirect_url': self.get_success_url()})
            return HttpResponseRedirect(self.get_success_url())
        else:
            if is_ajax:
                return JsonResponse({'success': False, 'errors': form.errors}, status=400)
            return self.form_invalid(form)

    def create_confirmed_reservation(self, user, court, res_date, start_time, end_time):
        Reservation.objects.create(
            user=user,
            court=court,
            start_time=datetime.combine(res_date, start_time),
            end_time=datetime.combine(res_date, end_time),
            status='CONFIRMED'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['facility'] = self.facility
        context.update(kwargs) # Dodaj dodatkowe dane, np. z handle_timeline_post
        return context

    def form_valid(self, form, is_ajax=False): # Ten form jest teraz pusty, dane bierzemy z POST
        # Logika dla zbiorczego tworzenia rezerwacji z podsumowania
        courts = self.request.POST.getlist('court_id')
        starts = self.request.POST.getlist('start_time')
        ends = self.request.POST.getlist('end_time')
        res_date_str = self.request.POST.get('reservation_date')
        
        if not all([courts, starts, ends, res_date_str]):
            error_msg = "Brak kompletnych danych do utworzenia rezerwacji."
            if is_ajax:
                form.add_error(None, error_msg)
                return False
            return HttpResponseBadRequest(error_msg)

        reservation_date = datetime.strptime(res_date_str, '%Y-%m-%d').date()

        for i in range(len(courts)):
            court = get_object_or_404(Court, pk=courts[i])
            start_time = datetime.strptime(starts[i], '%H:%M:%S').time()
            end_time = datetime.strptime(ends[i], '%H:%M:%S').time()

            reservation = Reservation(
                user=self.request.user,
                court=court,
                start_time=datetime.combine(reservation_date, start_time),
                end_time=datetime.combine(reservation_date, end_time),
                status='PENDING'
            )
            reservation.save()
            # Powiadomienie dla właściciela o nowej rezerwacji
            owner = reservation.court.facility.owner
            message = f"Nowa rezerwacja od {self.request.user.get_full_name()} na korcie nr {reservation.court.court_number} oczekuje na Twoją akceptację."
            notify_user(owner, message)
        
        return True


    def get_success_url(self):
        return reverse('courts:facility-detail', kwargs={'pk': self.facility.pk})

class CreateFacilityView(LoginRequiredMixin, CreateView):
    model = TennisFacility
    form_class = TennisFacilityForm
    template_name = 'courts/facility_form.html'
    success_url = reverse_lazy('courts:facility-list')

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class UpdateFacilityView(LoginRequiredMixin, UpdateView):
    model = TennisFacility
    form_class = TennisFacilityForm
    template_name = 'courts/facility_form.html'
    context_object_name = 'facility'

    def get_queryset(self):
        return TennisFacility.objects.filter(owner=self.request.user)

    def get_success_url(self):
        return reverse('courts:facility-detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_edit'] = True
        return context


class CourtCreateView(LoginRequiredMixin, CreateView):
    model = Court
    form_class = CourtForm
    template_name = 'courts/court_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.facility = get_object_or_404(TennisFacility, pk=self.kwargs['facility_pk'])
        if self.facility.owner != self.request.user:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.facility = self.facility
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['facility'] = self.facility
        return context

    def get_success_url(self):
        return reverse('courts:facility-detail', kwargs={'pk': self.facility.pk})

class CourtUpdateView(LoginRequiredMixin, UpdateView):
    model = Court
    form_class = CourtForm
    template_name = 'courts/court_form.html'
    context_object_name = 'court'

    def get_queryset(self):
        # Allow editing only by facility owner
        return Court.objects.filter(facility__owner=self.request.user)

    def get_success_url(self):
        return reverse('courts:facility-detail', kwargs={'pk': self.object.facility.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['facility'] = self.object.facility
        context['is_edit'] = True
        return context


class UpdateReservationStatusView(LoginRequiredMixin, UserPassesTestMixin, View):
    """
    Widok do aktualizacji statusu rezerwacji.
    Dostępny tylko dla właściciela obiektu.
    """
    def test_func(self):
        reservation = get_object_or_404(Reservation, pk=self.kwargs['pk'])
        status_to_set = self.kwargs.get('status')

        # Opiekun obiektu może zatwierdzić rezerwację, która oczekuje na akceptację.
        if reservation.court and reservation.court.facility.owner == self.request.user:
            if reservation.status == 'PENDING' and status_to_set in ['CONFIRMED', 'REJECTED']:
                return True
            # Właściciel może też zatwierdzić rezerwację po zmianie przez użytkownika (jeśli jest taka potrzeba)
            # lub jeśli sam chce ją ponownie zatwierdzić po jakiejś modyfikacji.
            if reservation.status == 'CHANGED' and status_to_set == 'CONFIRMED':
                return True

        # Użytkownik, który złożył rezerwację, może ją zatwierdzić po zmianach wprowadzonych przez opiekuna.
        if reservation.user == self.request.user and reservation.status in ['REJECTED', 'CHANGED'] and status_to_set == 'CONFIRMED':
            return True

        return False

    def post(self, request, *args, **kwargs):
        reservation = get_object_or_404(Reservation, pk=kwargs['pk'])
        new_status = kwargs['status']
        user_to_notify = reservation.user
        owner = reservation.court.facility.owner

        # Logika powiadomień
        if new_status == 'CONFIRMED' and request.user == owner:
            message = f"Twoja rezerwacja na korcie '{reservation.court}' w dniu {reservation.start_time.strftime('%d.%m.%Y %H:%M')} została potwierdzona."
            notify_user(user_to_notify, message)
        elif new_status == 'REJECTED' and request.user == owner:
            message = f"Twoja rezerwacja na korcie '{reservation.court}' w dniu {reservation.start_time.strftime('%d.%m.%Y %H:%M')} została odrzucona."
            notify_user(user_to_notify, message)
        
        reservation.status = kwargs['status']
        reservation.save()

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})

        # Przekierowuje z powrotem na stronę szczegółów obiektu
        return HttpResponseRedirect(reverse('courts:facility-detail', kwargs={'pk': reservation.court.facility.pk}))


class DeleteReservationView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """Widok do usuwania rezerwacji przez właściciela obiektu lub przez użytkownika, jeśli została odrzucona."""
    model = Reservation
    template_name = 'courts/reservation_confirm_delete.html' # Opcjonalnie, jeśli chcesz stronę potwierdzenia

    def test_func(self):
        reservation = self.get_object()
        user = self.request.user

        # Właściciel obiektu może usunąć rezerwację.
        if reservation.court.facility.owner == user:
            return True
        
        # Użytkownik może usunąć swoją rezerwację, jeśli ma status 'REJECTED'.
        if reservation.user == user and reservation.status in ['REJECTED', 'PENDING', 'CONFIRMED']:
            return True
        return False

    def form_valid(self, form):
        reservation = self.get_object()
        owner = reservation.court.facility.owner

        if self.request.user == owner and reservation.user != owner:
            message = f"Twoja rezerwacja na korcie '{reservation.court}' z dnia {reservation.start_time.strftime('%d.%m.%Y %H:%M')} została usunięta przez właściciela."
            notify_user(reservation.user, message)
        elif self.request.user == reservation.user and reservation.status in ['PENDING', 'CONFIRMED']:
            message = f"Użytkownik {self.request.user.get_full_name()} anulował swoją rezerwację na korcie '{reservation.court}' na dzień {reservation.start_time.strftime('%d.%m.%Y %H:%M')}."
            notify_user(owner, message)

        return super().form_valid(form)

    def post(self, request, *args, **kwargs):
        if request.headers.get('X-Requested-with') == 'XMLHttpRequest':
            self.object = self.get_object()
            self.form_valid(self.get_form(self.get_form_class()))
            return JsonResponse({'success': True})
        return super().post(request, *args, **kwargs)

    def get_success_url(self):
        # Po usunięciu wróć do widoku szczegółów obiektu
        if not hasattr(self, 'object') or not self.object:
             self.object = self.get_object()
        return reverse('courts:facility-detail', kwargs={'pk': self.object.court.facility.pk})
