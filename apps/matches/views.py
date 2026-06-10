from django.shortcuts import redirect

def results(request):
    return redirect('/astro/matches')

def summary(request):
    return redirect('/astro/matches')

def remove_match(request, *args, **kwargs):
    return redirect('/astro/matches')

def add_match(request):
    return redirect('/astro/matches')

def edit_match(request, *args, **kwargs):
    return redirect('/astro/matches')

def match_detail(request, *args, **kwargs):
    return redirect('/astro/matches')
