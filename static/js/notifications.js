// tennis-club.js

document.addEventListener('DOMContentLoaded', function () {
    const notificationsCountElement = document.getElementById('notifications-count');
    const notificationsDropdownMenu = document.getElementById('notifications-dropdown-menu');
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

    function fetchNotifications() {
        fetch('/notifications/api/notifications/')
            .then(response => response.json())
            .then(data => {
                const notifications = data.notifications;
                const count = data.count;

                if (notificationsCountElement) {
                    notificationsCountElement.textContent = count;
                    notificationsCountElement.style.display = count > 0 ? 'inline-block' : 'none';
                }

                if (notificationsDropdownMenu) {
                    notificationsDropdownMenu.innerHTML = '';
                    if (notifications.length === 0) {
                        notificationsDropdownMenu.innerHTML = '<li><a class="dropdown-item" href="#">Brak nowych powiadomień</a></li>';
                    } else {
                        notifications.forEach(notification => {
                            const listItem = document.createElement('li');
                            listItem.innerHTML = `
                                <a class="dropdown-item" href="#">
                                    ${notification.message}
                                    <small class="text-muted ms-2">${notification.created_at}</small>
                                </a>
                            `;
                            notificationsDropdownMenu.appendChild(listItem);
                        });
                        const readAllItem = document.createElement('li');
                        readAllItem.innerHTML = '<hr class="dropdown-divider"><a class="dropdown-item" href="#" id="mark-all-read">Oznacz wszystko jako przeczytane</a>';
                        notificationsDropdownMenu.appendChild(readAllItem);

                        document.getElementById('mark-all-read').addEventListener('click', handleMarkAllRead);
                    }
                }
            })
            .catch(error => {
                console.error('Error fetching notifications:', error);
                if (notificationsCountElement) {
                    notificationsCountElement.style.display = 'none';
                }
            });
    }

    function handleMarkAllRead(event) {
        event.preventDefault();
        fetch('/notifications/api/notifications/read_all/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                fetchNotifications();
            } else {
                console.error('Error marking notifications as read:', data.error);
            }
        })
        .catch(error => {
            console.error('Error marking notifications as read:', error);
        });
    }

    fetchNotifications();
});