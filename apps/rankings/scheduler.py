import threading
import time
import logging

logger = logging.getLogger(__name__)

def run_rebuild_loop():
    # Odczekaj chwilę na pełne zainicjalizowanie Django i bazy danych
    time.sleep(10)
    logger.info("Uruchomiono wątek automatycznego przeliczania rankingu w tle.")
    while True:
        try:
            from apps.rankings.services.ranking_calculator import rebuild_rankings
            logger.info("Rozpoczęcie automatycznego przeliczania rankingu...")
            count = rebuild_rankings()
            logger.info(f"Zakończono automatyczne przeliczanie rankingu. Zaktualizowano {count} wpisów.")
        except Exception as e:
            logger.error(f"Błąd podczas automatycznego przeliczania rankingu w tle: {e}", exc_info=True)
        
        # Czekaj 1 godzinę (3600 sekund)
        time.sleep(3600)

def start_background_scheduler():
    thread = threading.Thread(target=run_rebuild_loop, name="RankingRebuildThread", daemon=True)
    thread.start()
