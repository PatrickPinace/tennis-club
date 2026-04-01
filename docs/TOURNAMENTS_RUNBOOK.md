# Tournament Module - Operations Runbook

## Overview
This runbook provides practical guidance for managing and troubleshooting the tournament system. For technical constraints and validation rules, see `TOURNAMENTS_CONSTRAINTS.md`.

---

## Quick Start: Running a Tournament

### Prerequisites
- User must have `is_staff=True` or `is_superuser=True` to create tournaments
- At least 2 confirmed participants required
- Tournament type: `single_elimination` (only format supported in MVP)

### Standard Tournament Flow

```
1. CREATE tournament (draft status)
   ↓
2. OPEN REGISTRATION (registration_open)
   ↓
3. Users JOIN tournament
   ↓
4. CLOSE REGISTRATION (registration_closed)
   ↓
5. CONFIRM PARTICIPANTS (participants_confirmed)
   ↓
6. GENERATE BRACKET (bracket_ready)
   ↓
7. START TOURNAMENT (in_progress)
   ↓
8. REPORT MATCH RESULTS (one by one)
   ↓
9. FINISH TOURNAMENT (finished)
```

### Step-by-Step Guide

#### 1. Create Tournament
```bash
POST /api/tournaments/
{
  "name": "Turniej Klubowy - Kwiecień 2026",
  "description": "Turniej singlowy open",
  "tournament_type": "single_elimination",
  "match_format": "singles",
  "visibility": "public",
  "registration_mode": "auto",
  "start_date": "2026-04-15T10:00:00Z",
  "end_date": "2026-04-15T18:00:00Z",
  "registration_deadline": "2026-04-14T23:59:59Z",
  "min_participants": 4,
  "max_participants": 16,
  "facility_id": 1,
  "rank": 1
}
```

**Response:**
```json
{
  "id": 123,
  "name": "Turniej Klubowy - Kwiecień 2026",
  "status": "draft",
  "message": "Turniej został utworzony."
}
```

#### 2. Open Registration
```bash
POST /api/tournaments/123/open-registration/
```

**Response:**
```json
{
  "message": "Zapisy zostały otwarte."
}
```

**Tournament status:** `draft` → `registration_open`

#### 3. Close Registration
```bash
POST /api/tournaments/123/close-registration/
```

**Response:**
```json
{
  "message": "Zapisy zostały zamknięte."
}
```

**Tournament status:** `registration_open` → `registration_closed`

#### 4. Confirm Participants
```bash
POST /api/tournaments/123/confirm-participants/
```

**Response:**
```json
{
  "message": "Skład został zatwierdzony."
}
```

**Tournament status:** `registration_closed` → `participants_confirmed`

**Validation:**
- Minimum `min_participants` confirmed
- Error example: "Zbyt mała liczba uczestników. Minimum: 4, obecnie: 3."

#### 5. Generate Bracket
```bash
POST /api/tournaments/123/generate-bracket/
```

**Response:**
```json
{
  "message": "Drabinka została wygenerowana.",
  "num_matches": 7
}
```

**Tournament status:** `participants_confirmed` → `bracket_ready`

**What happens:**
- Creates all matches for single elimination bracket
- Applies seeding if configured
- Calculates rounds based on participant count (next power of 2)
- Example: 5 participants → 8-person bracket (3 byes in round 1)

#### 6. Start Tournament
```bash
POST /api/tournaments/123/start/
```

**Response:**
```json
{
  "message": "Turniej został rozpoczęty."
}
```

**Tournament status:** `bracket_ready` → `in_progress`

#### 7. Report Match Results
```bash
POST /api/tournament-matches/456/report-result/
{
  "set1_p1": 6,
  "set1_p2": 4,
  "set2_p1": 6,
  "set2_p2": 3
}
```

**Response:**
```json
{
  "message": "Wynik został raportowany.",
  "winner": "Jan Kowalski"
}
```

**What happens:**
- Match status: `scheduled` → `completed`
- Winner automatically advances to next match
- Loser marked as eliminated (or gets final position if in final)

**With 3rd set:**
```json
{
  "set1_p1": 6,
  "set1_p2": 4,
  "set2_p1": 3,
  "set2_p2": 6,
  "set3_p1": 7,
  "set3_p2": 5
}
```

#### 8. Finish Tournament
```bash
POST /api/tournaments/123/finish/
```

**Response:**
```json
{
  "message": "Turniej został zakończony.",
  "winner": "Jan Kowalski"
}
```

**Tournament status:** `in_progress` → `finished`

**Validation:**
- All matches must be completed
- Winner determined from final match
- Final positions calculated automatically

---

## Common Operations

### Viewing Tournament Details
```bash
GET /api/tournaments/123/
```

**Response includes:**
- Tournament info (name, dates, status, etc.)
- All participants with their status
- All matches with results
- Winner (if finished)
- Configuration (scoring rules, seeding, etc.)

### Viewing Bracket
```bash
GET /api/tournaments/123/bracket/
```

**Response:**
```json
{
  "bracket": [
    {
      "id": 1,
      "round": 1,
      "position": 1,
      "player1": "Jan Kowalski",
      "player2": "Anna Nowak",
      "winner": "Jan Kowalski",
      "status": "completed",
      "sets": [
        {"p1": 6, "p2": 4},
        {"p1": 6, "p2": 2}
      ]
    },
    ...
  ]
}
```

### Cancelling a Tournament
```bash
POST /api/tournaments/123/cancel/
{
  "reason": "Zła pogoda - kort zalany"
}
```

**Response:**
```json
{
  "message": "Turniej został anulowany."
}
```

**Can be cancelled from any status except `finished`**

---

## User Participation

### Joining a Tournament
**User action:**
```bash
POST /api/tournaments/123/join/
```

**Response:**
```json
{
  "id": 789,
  "status": "confirmed",
  "message": "Pomyślnie zapisano do turnieju."
}
```

**Participant status depends on `registration_mode`:**
- `auto`: Immediately `confirmed`
- `approval_required`: Initially `pending`, needs manager approval

### Withdrawing from Tournament
**User action:**
```bash
POST /api/tournaments/123/withdraw/
{
  "reason": "Kontuzja kolana"
}
```

**Response:**
```json
{
  "message": "Pomyślnie wypisano z turnieju."
}
```

**Important:**
- Users can self-withdraw only before `participants_confirmed`
- After confirmation, only manager can withdraw participant
- Withdrawal after bracket generation triggers walkover

---

## Manager Operations

### Approving Participants (for `approval_required` mode)
```bash
POST /api/tournaments/123/approve-participant/
{
  "participant_id": 789,
  "approved": true
}
```

**Response:**
```json
{
  "message": "Uczestnik został zatwierdzony."
}
```

**To reject:**
```json
{
  "participant_id": 789,
  "approved": false
}
```

### Force Withdraw Participant (after confirmation)
```bash
POST /api/tournaments/123/withdraw/
{
  "user_id": 456,  # Different from logged-in user
  "reason": "Nie pojawił się na turnieju"
}
```

**What happens:**
- Participant marked as `withdrawn`
- If they have an active match, opponent gets walkover
- Opponent automatically advances to next round

---

## Troubleshooting

### Error: "Tournament is full"
**Cause:** `current_count >= max_participants`

**Solutions:**
1. Increase `max_participants`:
   ```bash
   PATCH /api/tournaments/123/
   {
     "max_participants": 32
   }
   ```
2. Or wait for someone to withdraw

### Error: "Zbyt mała liczba uczestników"
**Cause:** `confirmed_count < min_participants`

**Solutions:**
1. Wait for more participants to join
2. Decrease `min_participants` (not recommended for bracket quality)
3. Manually approve more participants (if using `approval_required` mode)

### Error: "Drabinka już została wygenerowana"
**Cause:** Attempting to generate bracket twice

**Solution:**
This is by design (idempotent operation). If you need to regenerate:
1. In development/testing: Manually delete all TournamentMatch records for this tournament
2. In production: Contact admin - bracket regeneration requires special handling

**SQL (DANGEROUS - use only in development):**
```sql
DELETE FROM tournament_matches WHERE tournament_id = 123;
UPDATE tournaments SET status = 'participants_confirmed' WHERE id = 123;
```

### Error: "Nie można zakończyć turnieju. X meczów nie zostało rozliczonych"
**Cause:** Some matches still have status `scheduled`, `ready`, or `in_progress`

**Solution:**
```bash
# Find unfinished matches
GET /api/tournaments/123/bracket/
# Look for matches with status != "completed" and status != "walkover"

# Report results for each unfinished match
POST /api/tournament-matches/{match_id}/report-result/
{
  "set1_p1": 6,
  "set1_p2": 4,
  "set2_p1": 6,
  "set2_p2": 3
}
```

### Error: "Wynik tego meczu został już raportowany"
**Cause:** Match already completed

**Solution:**
This is actually success (idempotent operation). If result is incorrect:
1. Manual fix required - contact admin
2. Admin can update match directly in Django admin or database

### User Can't Join Tournament
**Possible causes:**
1. Registration not open (`status != 'registration_open'`)
   - Check: `GET /api/tournaments/123/` → look at `status` field
   - Fix: Manager needs to open registration
2. Past deadline (`now() > registration_deadline`)
   - Check: Compare current time with `registration_deadline`
   - Fix: Extend deadline if appropriate
3. Tournament full (`current_count >= max_participants`)
   - Check: Compare `participant_count` with `max_participants`
   - Fix: Increase `max_participants` or wait for withdrawal
4. Already registered
   - Check: Look for user in `participants` list
   - This is expected behavior (idempotent)

---

## Monitoring & Logs

### Event Logs
All tournament actions are logged to `TournamentEventLog`.

**View via Django admin:**
```
Admin → Tournament Event Logs → Filter by tournament
```

**Query via database:**
```sql
SELECT
  event_type,
  actor_id,
  payload,
  created_at
FROM tournament_event_logs
WHERE tournament_id = 123
ORDER BY created_at DESC;
```

**Event types:**
- `created` - Tournament created
- `registration_opened` - Registration opened
- `registration_closed` - Registration closed
- `participant_joined` - User joined
- `participant_approved` - Manager approved participant
- `participant_rejected` - Manager rejected participant
- `participant_withdrawn` - Participant withdrew
- `participants_confirmed` - Final roster confirmed
- `bracket_generated` - Bracket generated
- `tournament_started` - Tournament started
- `match_result` - Match result reported
- `match_walkover` - Walkover awarded
- `tournament_finished` - Tournament finished
- `tournament_cancelled` - Tournament cancelled

### Checking Tournament Health

**Current status:**
```bash
GET /api/tournaments/123/
```

**Key fields to check:**
- `status` - Current stage
- `participant_count` vs `min_participants` / `max_participants`
- `matches` - Count of completed vs total

**Dashboard query (all active tournaments):**
```bash
GET /api/tournaments/?status=in_progress
```

---

## Performance Considerations

### High Registration Volume
For tournaments expecting >50 participants:
1. Increase `max_participants` ahead of time
2. Consider using `approval_required` mode to control flow
3. Monitor database locks during registration rush

### Large Brackets
For tournaments with >32 participants:
- Bracket generation may take 2-3 seconds
- Result reporting is fast (single match update)
- Frontend should show loading state

### Concurrent Access
Multiple managers can safely:
- ✅ Report different match results simultaneously
- ✅ View tournament details
- ❌ Generate bracket simultaneously (second call will return existing)
- ❌ Finish tournament simultaneously (second call will return success)

All critical operations use row-level locking to prevent race conditions.

---

## API Reference Summary

### Tournament Management (Manager Only)
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/tournaments/` | Create tournament |
| POST | `/api/tournaments/{id}/open-registration/` | Open registration |
| POST | `/api/tournaments/{id}/close-registration/` | Close registration |
| POST | `/api/tournaments/{id}/confirm-participants/` | Confirm roster |
| POST | `/api/tournaments/{id}/generate-bracket/` | Generate bracket |
| POST | `/api/tournaments/{id}/start/` | Start tournament |
| POST | `/api/tournament-matches/{id}/report-result/` | Report match result |
| POST | `/api/tournaments/{id}/finish/` | Finish tournament |
| POST | `/api/tournaments/{id}/cancel/` | Cancel tournament |
| POST | `/api/tournaments/{id}/approve-participant/` | Approve/reject participant |

### Public Actions
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/tournaments/` | List tournaments |
| GET | `/api/tournaments/{id}/` | View details |
| GET | `/api/tournaments/{id}/bracket/` | View bracket |
| POST | `/api/tournaments/{id}/join/` | Join tournament |
| POST | `/api/tournaments/{id}/withdraw/` | Withdraw from tournament |

---

## Emergency Procedures

### Reset Tournament to Previous Stage
⚠️ **Use only in development or with admin approval**

```python
# Django shell
from v2_core.models import Tournament, TournamentMatch

# Reset from bracket_ready to participants_confirmed
tournament = Tournament.objects.get(id=123)
tournament.status = 'participants_confirmed'
tournament.save()
TournamentMatch.objects.filter(tournament=tournament).delete()
```

### Fix Incorrect Match Result
⚠️ **Admin only - manual database update required**

```python
# Django shell
from v2_core.models import TournamentMatch

match = TournamentMatch.objects.get(id=456)
match.set1_p1 = 6
match.set1_p2 = 4
match.set2_p1 = 6
match.set2_p2 = 3
match.set3_p1 = None
match.set3_p2 = None

# Recalculate winner
if (match.set1_p1 > match.set1_p2) + (match.set2_p1 > match.set2_p2) > 1:
    match.winner_participant = match.player1_participant
    match.loser_participant = match.player2_participant
else:
    match.winner_participant = match.player2_participant
    match.loser_participant = match.player1_participant

match.save()

# You may need to manually update subsequent matches!
```

### Recover from Failed Transaction
**Symptom:** Tournament stuck in intermediate state after error

**Check transaction logs:**
```bash
# Check recent event logs
GET /api/tournaments/123/
# Look at last event in TournamentEventLog

# Check database state
SELECT status FROM tournaments WHERE id = 123;
SELECT status, COUNT(*) FROM tournament_participants WHERE tournament_id = 123 GROUP BY status;
SELECT status, COUNT(*) FROM tournament_matches WHERE tournament_id = 123 GROUP BY status;
```

**Recovery:**
1. Identify last successful step from event log
2. Verify database state matches expected state for that step
3. If mismatch, manually correct via Django shell (admin only)
4. Retry failed operation

---

## Contact & Support

For issues not covered in this runbook:
1. Check `TOURNAMENTS_CONSTRAINTS.md` for technical details
2. Check `TournamentEventLog` for audit trail
3. Contact system administrator with tournament ID and error message

---

Last updated: 2026-04-01
Version: 1.0 (MVP)
