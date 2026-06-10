# Instrukcja: Obliczanie Punktów Rankingowych w Klubie Tenisa

Niniejsza instrukcja opisuje szczegółowo algorytm i zasady obliczania punktów rankingowych graczy w systemie. Całość logiki kalkulatora znajduje się w pliku [ranking_calculator.py](file:///c:/Users/Lucjan/Desktop/Klub%20Tenisa/apps/rankings/services/ranking_calculator.py).

---

## 1. Założenia Ogólne
1. **Początkowa liczba punktów:** Każdy nowy gracz startuje z bazową liczbą **1000.00 punktów**.
2. **Kolejność obliczeń:** Mecze są przetwarzane chronologicznie według daty zaplanowania (`scheduled_time`) lub daty rozpoczęcia turnieju (`start_date`), a następnie według numeru rundy i indeksu meczu.
3. **Uwzględniane mecze:**
   - Turniej musi mieć status **Zakończony (FINISHED)** lub **Aktywny (ACTIVE)**.
   - Turniej musi być rankingowy (`is_ranked=True`).
   - Mecz musi być w odpowiednim formacie (`SNG` dla singla, `DBL` dla debla).
   - Status meczu musi być **Zakończony (COMPLETED)** lub **Walkower (WITHDRAWN)**.

---

## 2. Algorytm Obliczania Punktów (Elo)

Zaimplementowany system opiera się na zmodyfikowanym rankingu **Elo**. Punkty są przeliczane po każdym meczu według poniższego schematu.

### Krok A: Określenie ratingu gracza / zespołu
Dla meczów deblowych brana jest pod uwagę średnia arytmetyczna punktów obu członków drużyny:
- **Rating Zespołu 1 ($R_1$):** średnia punktów graczy z pierwszego zespołu.
- **Rating Zespołu 2 ($R_2$):** średnia punktów graczy z drugiego zespołu.

### Krok B: Obliczenie oczekiwanego wyniku (Probability)
Oczekiwane prawdopodobieństwo wygranej dla każdego z zespołów wyliczane jest ze wzoru:

$$E_1 = \frac{1}{1 + 10^{\frac{R_2 - R_1}{400}}}$$

$$E_2 = 1 - E_1$$

*Gdzie $E_1$ to oczekiwany wynik Zespołu 1, a $E_2$ to oczekiwany wynik Zespołu 2.*

### Krok C: Rzeczywisty wynik meczu ($S$)
W zależności od rezultatu meczu, przypisywane są następujące wartości:
- Wygrana Zespołu 1: $S_1 = 1$, $S_2 = 0$
- Wygrana Zespołu 2: $S_1 = 0$, $S_2 = 1$
- Remis: $S_1 = 0.5$, $S_2 = 0.5$

### Krok D: Współczynnik Wagi Meczu (K-factor)
Współczynnik K określa maksymalną liczbę punktów, jaką można zyskać lub stracić w jednym meczu. Wartość bazowa zależy od rangi turnieju (`rank` w modelu turnieju):
- **Ranga 1:** $K_{base} = 50$
- **Ranga 2:** $K_{base} = 30$
- **Pozostałe rangi:** $K_{base} = 15$

#### Mnożnik Rundy (Match Multiplier)
Dla turniejów pucharowych (pojedynczej lub podwójnej eliminacji) waga meczu rośnie w decydujących fazach turnieju:
- **Finał / Finał Pocieszenia (3. miejsce) / Grand Final:** Mnożnik wynosi **$1.5$**
- **Półfinał:** Mnożnik wynosi **$1.25$**
- **Pozostałe rundy:** Mnożnik wynosi **$1.0$** (jak również dla wszystkich innych typów turniejów, np. kołowych/ligowych).

Ostateczny współczynnik $K_{final}$ to:
$$K_{final} = K_{base} \times Mno\dot{z}nik$$

### Krok E: Zmiana Punktowa
Różnica punktowa dopisywana (lub odejmowana) do rankingu każdego gracza w danym zespole wynosi:

$$\Delta P_1 = K_{final} \times (S_1 - E_1)$$

$$\Delta P_2 = K_{final} \times (S_2 - E_2)$$

Wyniki są zaokrąglane do 2 miejsc po przecinku.

---

## 3. Bonusy za Udział w Turnieju

Po przeliczeniu wszystkich meczów, do końcowych punktów gracza dodawany jest jednorazowy bonus za udział w każdym turnieju:
- Warunkiem otrzymania bonusu jest rozegranie przez gracza przynajmniej jednego **zakończonego meczu (status COMPLETED)** w danym turnieju.
- Wartość bonusu pobierana jest z konfiguracji rang w bazie danych (model `TournamentRankPoints`, pole `participation_bonus`).

---

## 4. Spadek za Nieaktywność (Inactivity Decay)

W celu motywowania graczy do regularnej gry, wprowadzony został mechanizm kary za brak aktywności:
- **Dotyczy wyłącznie rankingu ogólnego (wszech czasów)** — nie jest stosowany w rankingach sezonowych.
- Jeżeli gracz nie rozegrał żadnego meczu przez **ponad 30 dni**, jego ranking jest pomniejszany za każdy kolejny tydzień nieaktywności:
  $$punkty\_karne = \lfloor \frac{dni\_nieaktywno\acute{s}ci - 30}{7} \rfloor \times 5$$
- Punkty rankingowe gracza po odliczeniu kary nie mogą spaść poniżej wartości `0.00`.

---

## 5. Klasyfikacja i Miejsca w Rankingu (Tie-breaking)

Po zsumowaniu wszystkich punktów, gracze są sortowani według następujących kryteriów (w kolejności malejącej):
1. **Punkty rankingowe**
2. **Liczba wygranych meczów**
3. **Liczba wygranych setów**

W przypadku, gdy dwóch lub więcej graczy posiada identyczne wartości we wszystkich trzech powyższych kryteriach, zajmują oni **to samo miejsce (ex aequo)** w tabeli rankingowej.
