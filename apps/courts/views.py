from django.shortcuts import redirect

def facility_list(request):
    return redirect('/astro/rezerwacje-kortow')

def reservations(request):
    return redirect('/astro/courts/reservations')

def redirect_to_reservations(request, *args, **kwargs):
    return redirect('/astro/courts/reservations')
