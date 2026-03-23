document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.reaction-btn').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation(); // Zapobiega przejściu do szczegółów meczu

            const matchId = this.dataset.matchId;
            const emoji = this.dataset.emoji;
            const url = `/tournaments/match/${matchId}/react/`;

            fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: `emoji=${encodeURIComponent(emoji)}`
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'ok') {
                    // Znajdź licznik dla tego przycisku
                    const countSpan = this.querySelector('.reaction-count');
                    if (countSpan) {
                        countSpan.textContent = data.count;
                    }
                    // Zmień styl przycisku (toggle active)
                    this.classList.toggle('active', data.action === 'added');
                } else {
                    console.error('Błąd reakcji:', data.message);
                }
            })
            .catch(error => console.error('Błąd sieci:', error));
        });
    });
});

// Funkcja pomocnicza do pobierania tokena CSRF
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}