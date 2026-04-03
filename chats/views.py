from datetime import datetime
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Max
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from .forms import MessageForm
from apps.friends.models import Friend
from .models import ChatMessage, ChatImage, TournamentMatchChatMessage

User = get_user_model()


class InboxView(LoginRequiredMixin, View):
    """
    Widok skrzynki odbiorczej, wyświetlający listę konwersacji.
    """
    def get(self, request):
        # Znajdź ID użytkowników, z którymi rozmawiał zalogowany użytkownik
        contacted_user_ids = ChatMessage.objects.filter(
            Q(sender=request.user) | Q(recipient=request.user)
        ).values_list('sender_id', 'recipient_id')

        # Stwórz płaską listę unikalnych ID, wykluczając własne ID
        user_ids = {uid for t in contacted_user_ids for uid in t if uid != request.user.id}

        # Pobierz znajomych użytkownika, z którymi nie ma jeszcze konwersacji
        friend_ids = Friend.objects.filter(user=request.user).values_list('friend_id', flat=True)
        new_contacts_ids = set(friend_ids) - user_ids
        friends_to_chat_with = User.objects.filter(id__in=new_contacts_ids).order_by('first_name', 'last_name')

        # Pobierz ostatnią wiadomość dla każdej konwersacji
        latest_messages = []
        for user_id in user_ids:
            other_user = User.objects.get(id=user_id)
            message = ChatMessage.objects.get_conversation(request.user, other_user).last()
            unread_count = ChatMessage.objects.filter(sender=other_user, recipient=request.user, is_read=False).count()
            if message:
                latest_messages.append({
                    'message': message,
                    'unread_count': unread_count
                })

        # Sortuj konwersacje od najnowszej do najstarszej
        latest_messages.sort(key=lambda item: item['message'].timestamp, reverse=True)

        return render(request, 'chats/inbox.html', {
            'latest_messages': latest_messages,
            'friends_to_chat_with': friends_to_chat_with
        })


class ConversationView(LoginRequiredMixin, View):
    """
    Widok pojedynczej konwersacji z innym użytkownikiem.
    """
    def get(self, request, username):
        other_user = get_object_or_404(User, username=username)
        messages = ChatMessage.objects.get_conversation(request.user, other_user).prefetch_related('images')
        form = MessageForm()

        # Oznacz wiadomości jako przeczytane
        ChatMessage.objects.filter(sender=other_user, recipient=request.user, is_read=False).update(is_read=True)

        return render(request, 'chats/conversation.html', {
            'other_user': other_user,
            'messages': messages,
            'form': form
        })

    def post(self, request, username):
        other_user = get_object_or_404(User, username=username)
        form = MessageForm(request.POST, request.FILES)
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        if form.is_valid():
            content = form.cleaned_data.get('content')
            images = request.FILES.getlist('images')

            # Utwórz wiadomość
            message = ChatMessage.objects.create(
                sender=request.user,
                recipient=other_user,
                content=content
            )

            image_objects = []
            # Dodaj załączone obrazy do wiadomości
            for image_file in images:
                chat_image = ChatImage.objects.create(message=message, image=image_file)
                image_objects.append(chat_image)

            if is_ajax:
                images_data = [{'url': img.image.url} for img in image_objects]
                message_data = {
                    'id': message.id,
                    'sender_name': message.sender.get_full_name() or message.sender.username,
                    'content': message.content,
                    'timestamp': message.timestamp.isoformat(),
                    'is_sent_by_user': True, # Zawsze prawda, bo to jest wiadomość wysyłana
                    'images': images_data,
                }
                return JsonResponse({'message': message_data}, status=201)
            else:
                return redirect(reverse('chats:conversation', kwargs={'username': username}))

        # Jeśli formularz jest nieprawidłowy, ponownie wyrenderuj stronę z błędami
        if is_ajax:
            return JsonResponse({'errors': form.errors}, status=400)
        else:
            messages = ChatMessage.objects.get_conversation(request.user, other_user).prefetch_related('images')
            return render(request, 'chats/conversation.html', {
                'other_user': other_user,
                'messages': messages,
                'form': form
            })


class CheckNewMessagesView(LoginRequiredMixin, View):
    """
    Widok API do sprawdzania nowych wiadomości w konwersacji.
    """
    def get(self, request, username):
        other_user = get_object_or_404(User, username=username)
        last_timestamp_str = request.GET.get('last_timestamp')

        if not last_timestamp_str:
            return JsonResponse({'messages': []})

        try:
            # Konwertujemy timestamp z formatu ISO (z 'Z' na końcu)
            # Ponieważ USE_TZ=False, musimy usunąć informację o strefie czasowej po konwersji
            last_timestamp = datetime.fromisoformat(last_timestamp_str.replace('Z', '+00:00')).replace(tzinfo=None)
        except ValueError:
            return JsonResponse({'error': 'Invalid timestamp format'}, status=400)

        # Pobieramy nowe wiadomości
        new_messages = ChatMessage.objects.filter(
            (Q(sender=other_user, recipient=request.user) | Q(sender=request.user, recipient=other_user)) &
            Q(timestamp__gt=last_timestamp)
        ).order_by('timestamp').prefetch_related('images')

        # Oznaczamy jako przeczytane, jeśli nadawcą jest drugi użytkownik
        messages_to_mark_read = new_messages.filter(sender=other_user, is_read=False)
        if messages_to_mark_read.exists():
            messages_to_mark_read.update(is_read=True)

        # Przygotowujemy dane do wysłania jako JSON
        messages_data = []
        for message in new_messages:
            images_data = [{'url': img.image.url} for img in message.images.all()]
            messages_data.append({
                'id': message.id,
                'sender_name': message.sender.get_full_name() or message.sender.username,
                'content': message.content,
                'timestamp': message.timestamp.isoformat(),
                'is_sent_by_user': message.sender == request.user,
                'images': images_data,
            })

        return JsonResponse({'messages': messages_data})


class CheckNewMatchMessagesView(View):
    """
    Widok API do sprawdzania nowych wiadomości na czacie meczowym.
    Dostępny dla wszystkich, nie wymaga logowania do odczytu.
    """
    def get(self, request, match_pk):
        last_timestamp_str = request.GET.get('last_timestamp')

        if not last_timestamp_str:
            return JsonResponse({'messages': []})

        try:
            # Ponieważ USE_TZ=False, musimy usunąć informację o strefie czasowej po konwersji
            last_timestamp = datetime.fromisoformat(last_timestamp_str.replace('Z', '+00:00')).replace(tzinfo=None)
        except ValueError:
            return JsonResponse({'error': 'Invalid timestamp format'}, status=400)

        new_messages = TournamentMatchChatMessage.objects.filter(
            match_id=match_pk,
            timestamp__gt=last_timestamp
        ).order_by('timestamp').select_related('sender').prefetch_related('images')

        messages_data = []
        for message in new_messages:
            images_data = [{'url': img.image.url} for img in message.images.all()]
            
            is_sent_by_current_user = False
            if request.user.is_authenticated:
                is_sent_by_current_user = (message.sender == request.user)

            messages_data.append({
                'id': message.id,
                'sender_name': message.sender.get_full_name() or message.sender.username,
                'content': message.content,
                'timestamp': message.timestamp.isoformat(),
                'is_sent_by_user': is_sent_by_current_user,
                'images': images_data,
            })

        return JsonResponse({'messages': messages_data})