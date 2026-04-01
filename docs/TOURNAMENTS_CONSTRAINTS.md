# Tournament Module - Database Constraints & Validation

## Overview
This document describes validation rules and database constraints in the tournament module, with particular attention to differences between SQLite (development) and PostgreSQL (production).

## Critical Difference: SQLite vs PostgreSQL

### Reservation Overlap Prevention

**PostgreSQL (Production):**
```python
# In v2_core/models/facilities.py
ExclusionConstraint(
    name='reservations_no_overlap_per_court',
    expressions=[
        (TsTzRange('start_time', 'end_time', RangeBoundary()), RangeOperators.OVERLAPS),
        ('court', RangeOperators.EQUAL),
    ],
    condition=Q(status__in=['pending', 'confirmed'])
)
```
**Status:** ✅ ENABLED on production PostgreSQL
**Protection:** Database-level guarantee that no two active reservations can overlap on the same court.

**SQLite (Development):**
```python
# Note: ExclusionConstraint removed for SQLite compatibility
# Overlap validation MUST be handled in API layer
```
**Status:** ❌ NOT ENFORCED by database
**Protection:** API validation in `api_reservations.create_reservation()` line 297-320

⚠️ **Action Required Before Production:**
Verify that PostgreSQL constraints are properly applied during migration on production environment.

---

## Tournament Module Constraints

### Database-Level Constraints

#### 1. Tournament Model
```python
# Check constraint
models.CheckConstraint(
    condition=Q(max_participants__gte=F('min_participants')),
    name='tournaments_max_gte_min'
)

# Model-level validation (clean method)
- end_date > start_date
- max_participants >= min_participants
- min_participants >= 2
- registration_deadline <= start_date
```

#### 2. Participant Model
```python
# Unique constraint
unique_together = [['tournament', 'user']]

# Check constraint
models.CheckConstraint(
    condition=Q(seed__gte=1) | Q(seed__isnull=True),
    name='participants_seed_positive'
)
```

#### 3. TournamentMatch Model
```python
# Unique constraint
unique_together = [['tournament', 'round_number', 'match_number']]

# Indexes for performance
- Index on (tournament, status)
- Index on (scheduled_time)
- Index on (bracket_position)
```

#### 4. TournamentManager Model
```python
# Unique constraint
unique_together = [['tournament', 'user']]
```

---

## Service Layer Validation & Idempotency

### Transaction Safety & Race Condition Prevention

All critical operations use:
1. `@transaction.atomic` decorator
2. `select_for_update()` for row-level locking
3. Idempotency checks

#### Idempotent Operations (Safe to Call Multiple Times)

| Service Method | Protection | Behavior on Retry |
|----------------|-----------|-------------------|
| `confirm_participants()` | ✅ `select_for_update()` | Returns success if already confirmed |
| `generate_bracket()` | ✅ `select_for_update()` | Returns existing bracket |
| `report_result()` | ✅ `select_for_update()` | Returns existing result if already completed |
| `finish_tournament()` | ✅ `select_for_update()` | Returns success if already finished |
| `join_tournament()` | ✅ `select_for_update()` | Returns existing participant if already registered |

#### Race Condition Scenarios Protected

**Scenario 1: Double Registration**
```python
# Two users register for last tournament spot simultaneously
# Protection: select_for_update() locks tournament row during participant count check
tournament = Tournament.objects.select_for_update().get(pk=tournament.pk)
current_count = Participant.objects.filter(...).count()
if current_count >= tournament.max_participants:
    raise ValidationError('Tournament is full')
```

**Scenario 2: Simultaneous Bracket Generation**
```python
# Two managers click "Generate Bracket" at the same time
# Protection: Check for existing matches AFTER acquiring lock
tournament = Tournament.objects.select_for_update().get(pk=tournament.pk)
existing_matches = TournamentMatch.objects.filter(tournament=tournament)
if existing_matches.exists():
    return existing_matches  # Idempotent return
```

**Scenario 3: Simultaneous Result Reporting**
```python
# Two managers report result for same match
# Protection: Lock match row and check status
match = TournamentMatch.objects.select_for_update().get(pk=match.pk)
if match.status in ['completed', 'walkover']:
    return match  # Already completed, return existing
```

---

## Permission Validation

### Role-Based Access Control

#### System Roles
- `admin` (is_superuser): Full access to all tournaments
- `club_manager` (is_staff): Can create and manage tournaments
- `participant`: Tournament member (no management rights unless also manager)
- `user`: Regular user (can join public tournaments)

#### Permission Checks

**Tournament Creation:**
```python
def can_create_tournament(user: User) -> bool:
    return user.is_staff or user.is_superuser
```

**Tournament Management:**
```python
def is_tournament_manager(tournament: Tournament, user: User) -> bool:
    if user.is_superuser:
        return True
    return TournamentManager.objects.filter(
        tournament=tournament,
        user=user
    ).exists()
```

**API Endpoint Permissions:**

| Endpoint | Required Permission | Validation Location |
|----------|-------------------|---------------------|
| `POST /api/tournaments/` | `is_staff` or `is_superuser` | `TournamentCreationService.can_create_tournament()` |
| `POST /tournaments/{id}/open-registration/` | Tournament manager | `TournamentCreationService.is_tournament_manager()` |
| `POST /tournaments/{id}/close-registration/` | Tournament manager | ↑ |
| `POST /tournaments/{id}/cancel/` | Tournament manager | ↑ |
| `POST /tournaments/{id}/join/` | Authenticated user | None (any user can join public tournaments) |
| `POST /tournaments/{id}/withdraw/` | Self or manager | `TournamentRegistrationService.withdraw_from_tournament()` |
| `POST /tournaments/{id}/approve-participant/` | Tournament manager | `TournamentRegistrationService._is_tournament_manager()` |
| `POST /tournaments/{id}/confirm-participants/` | Tournament manager | ↑ |
| `POST /tournaments/{id}/generate-bracket/` | Tournament manager | `TournamentBracketService._is_tournament_manager()` |
| `POST /tournaments/{id}/start/` | Tournament manager | ↑ |
| `POST /tournament-matches/{id}/report-result/` | Tournament manager | `TournamentMatchService._is_tournament_manager()` |
| `POST /tournaments/{id}/finish/` | Tournament manager | ↑ |

⚠️ **Security Note:**
All management endpoints verify permissions in the service layer, NOT just in the API view. This ensures permissions cannot be bypassed even if called from console or background tasks.

---

## Status Transition Rules

### Tournament Status Flow
```
draft
  ↓ (open_registration)
registration_open
  ↓ (close_registration)
registration_closed
  ↓ (confirm_participants)
participants_confirmed
  ↓ (generate_bracket)
bracket_ready
  ↓ (start_tournament)
in_progress
  ↓ (finish_tournament)
finished

  ↓ (cancel_tournament - from any status except finished)
cancelled
```

### Participant Status Flow
```
pending (if approval_required)
  ↓ (approve)
confirmed
  ↓ (tournament progresses)
eliminated / winner

withdrawn (can happen at any stage, rules differ)
rejected (if manager rejects during approval)
```

### Match Status Flow
```
scheduled → ready → in_progress → completed
         ↘ walkover
         ↘ cancelled
```

---

## Business Rules Enforced

### Registration Rules
1. ✅ Cannot join if `status != 'registration_open'`
2. ✅ Cannot join after deadline
3. ✅ Cannot join if tournament is full (`current_count >= max_participants`)
4. ✅ Cannot join twice (unique constraint + idempotency check)
5. ✅ User can self-withdraw only before `participants_confirmed`
6. ✅ Manager can withdraw participant at any stage (triggers walkover if needed)

### Bracket Generation Rules
1. ✅ Only after `status == 'participants_confirmed'`
2. ✅ Requires `confirmed_count >= min_participants`
3. ✅ Can only generate once (idempotent - returns existing if called again)
4. ✅ Only `single_elimination` supported in MVP

### Match Result Rules
1. ✅ Both participants must be known
2. ✅ Cannot report result twice (idempotent - returns existing)
3. ✅ Winner automatically advances to next match
4. ✅ Set scores must be valid (set1 and set2 required, set3 optional)

### Tournament Finish Rules
1. ✅ Only when `status == 'in_progress'`
2. ✅ All matches must be completed
3. ✅ Winner must be determined from final match
4. ✅ Final positions calculated automatically
5. ✅ Event logged for audit trail

---

## Testing Recommendations

### Priority 1: Critical Path Tests
- [ ] Full tournament lifecycle (creation → registration → bracket → matches → finish)
- [ ] Race condition: Simultaneous registration for last spot
- [ ] Race condition: Simultaneous bracket generation
- [ ] Race condition: Simultaneous result reporting
- [ ] Idempotency: Call confirm_participants twice
- [ ] Idempotency: Call generate_bracket twice
- [ ] Idempotency: Call finish_tournament twice

### Priority 2: Permission Tests
- [ ] Regular user cannot create tournament
- [ ] Regular user cannot manage tournament (all 10+ management endpoints)
- [ ] Manager can manage only their tournaments
- [ ] Superuser can manage all tournaments

### Priority 3: Business Logic Tests
- [ ] Cannot register after deadline
- [ ] Cannot register after tournament is full
- [ ] Cannot confirm participants with too few registered
- [ ] Cannot generate bracket before participants confirmed
- [ ] Withdrawal after bracket triggers walkover
- [ ] Cannot finish tournament with unfinished matches

### Priority 4: PostgreSQL Production Tests
- [ ] Verify ExclusionConstraint works for reservations
- [ ] Verify all unique constraints enforced
- [ ] Verify check constraints enforced
- [ ] Performance test with select_for_update on high concurrency

---

## Known Limitations & Future Improvements

### Current MVP Limitations
1. Only `single_elimination` bracket format supported
2. Simplified final position calculation (only 1st and 2nd place)
3. Ranking points not yet implemented
4. No third-place match support (despite config field)
5. No double elimination
6. No round-robin tournament support

### Planned Improvements
1. Implement `TournamentSettlementService.award_ranking_points()`
2. Add full position calculation (3rd, 4th, quarterfinals, etc.)
3. Add round-robin tournament logic
4. Add doubles tournament support with partner pairing
5. Add API endpoint to regenerate bracket (for testing)
6. Add admin action to reset tournament to previous state

---

## Production Deployment Checklist

Before deploying to production:
- [ ] Run all migrations on production PostgreSQL
- [ ] Verify ExclusionConstraint is active: `SELECT * FROM pg_constraint WHERE conname = 'reservations_no_overlap_per_court'`
- [ ] Test reservation overlap prevention works
- [ ] Verify all tournament unique constraints: `SELECT * FROM pg_constraint WHERE conrelid = 'tournaments'::regclass`
- [ ] Load test: 100 simultaneous tournament registrations
- [ ] Load test: 10 simultaneous bracket generations
- [ ] Create superuser for tournament management
- [ ] Set `is_staff=True` for designated club managers
- [ ] Backup database before first production tournament
- [ ] Monitor TournamentEventLog for any errors during first tournament

---

Last updated: 2026-04-01
Version: 1.0 (MVP)
