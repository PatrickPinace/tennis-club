// Service Worker dla powiadomień push Tennis Club
const CACHE_NAME = 'tennis-club-v1';
const urlsToCache = [
    '/',
    '/static/css/tennis-club.css',
    '/static/js/tennis-club.js',
    '/static/img/logo.png',
    '/static/img/ball.png'
];

// Instalacja Service Worker
self.addEventListener('install', (event) => {
    console.log('Service Worker: Instalacja');
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {
                console.log('Service Worker: Cachowanie plików');
                return cache.addAll(urlsToCache);
            })
    );
});

// Aktywacja Service Worker
self.addEventListener('activate', (event) => {
    console.log('Service Worker: Aktywacja');
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME) {
                        console.log('Service Worker: Usuwanie starego cache', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
});

// Interceptowanie żądań sieciowych
self.addEventListener('fetch', (event) => {
    event.respondWith(
        caches.match(event.request)
            .then((response) => {
                // Zwróć z cache jeśli dostępne, w przeciwnym razie z sieci
                return response || fetch(event.request);
            })
    );
});

// Obsługa powiadomień push
self.addEventListener('push', (event) => {
    console.log('Service Worker: Otrzymano powiadomienie push');
    
    let notificationData = {
        title: 'Tennis Club',
        body: 'Nowe powiadomienie',
        icon: '/static/img/logo.png',
        badge: '/static/img/ball.png',
        tag: 'tennis-club-notification',
        requireInteraction: false,
        data: {
            url: '/'
        }
    };
    
    // Jeśli otrzymano dane z serwera
    if (event.data) {
        try {
            const data = event.data.json();
            notificationData = {
                ...notificationData,
                ...data
            };
        } catch (error) {
            console.log('Błąd podczas parsowania danych powiadomienia:', error);
        }
    }
    
    // Wyświetlenie powiadomienia
    event.waitUntil(
        self.registration.showNotification(notificationData.title, {
            body: notificationData.body,
            icon: notificationData.icon,
            badge: notificationData.badge,
            tag: notificationData.tag,
            requireInteraction: notificationData.requireInteraction,
            data: notificationData.data,
            actions: [
                {
                    action: 'open',
                    title: 'Otwórz',
                    icon: '/static/img/ball.png'
                },
                {
                    action: 'close',
                    title: 'Zamknij',
                    icon: '/static/img/ball.png'
                }
            ]
        })
    );
});

// Obsługa kliknięć w powiadomienia
self.addEventListener('notificationclick', (event) => {
    console.log('Service Worker: Kliknięto w powiadomienie', event.action);
    
    event.notification.close();
    
    if (event.action === 'close') {
        return;
    }
    
    // Otwarcie aplikacji
    event.waitUntil(
        clients.matchAll({
            type: 'window',
            includeUncontrolled: true
        }).then((clientList) => {
            // Jeśli aplikacja jest już otwarta, skup się na niej
            for (let i = 0; i < clientList.length; i++) {
                const client = clientList[i];
                if (client.url.includes(self.location.origin) && 'focus' in client) {
                    return client.focus();
                }
            }
            
            // Jeśli aplikacja nie jest otwarta, otwórz nową kartę
            if (clients.openWindow) {
                return clients.openWindow(event.notification.data.url || '/');
            }
        })
    );
});

// Obsługa zamknięcia powiadomień
self.addEventListener('notificationclose', (event) => {
    console.log('Service Worker: Powiadomienie zostało zamknięte');
});

// Obsługa wiadomości z głównej aplikacji
self.addEventListener('message', (event) => {
    console.log('Service Worker: Otrzymano wiadomość', event.data);
    
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
});
