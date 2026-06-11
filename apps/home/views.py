from django.shortcuts import render, redirect

def custom_404(request, exception):
    return render(request, '404.html', {}, status=404)

def custom_500(request):
    return render(request, '500.html', {}, status=500)

def home(request):
    if request.user.is_authenticated:
        return redirect('/astro/dashboard')  # Astro dashboard
    return redirect('/astro/login')  # Astro login page

def about_author(request):
    return redirect('/astro/kontakt')  # Astro kontakt / main page

def dashboard(request):
    return redirect('/astro/dashboard')

def privacy_policy(request):
    return redirect('/astro/polityka-prywatnosci')

