// Tournament types (Sprint 4)

export type TournamentStatus =
  | 'draft'
  | 'registration_open'
  | 'registration_closed'
  | 'participants_confirmed'
  | 'bracket_ready'
  | 'in_progress'
  | 'finished'
  | 'cancelled';

export type TournamentType = 'round_robin' | 'single_elimination';
export type TournamentFormat = 'singles' | 'doubles';
export type TournamentVisibility = 'public' | 'private' | 'invite_only';
export type RegistrationMode = 'auto' | 'approval_required';

export type ParticipantStatus =
  | 'pending'
  | 'confirmed'
  | 'waitlist'
  | 'withdrawn'
  | 'rejected'
  | 'eliminated'
  | 'winner';

export type TournamentMatchStatus =
  | 'waiting'
  | 'scheduled'
  | 'ready'
  | 'in_progress'
  | 'completed'
  | 'walkover'
  | 'cancelled';

export interface TournamentFacility {
  id: number;
  name: string;
}

export interface TournamentWinner {
  id: number;
  display_name: string;
}

export interface TournamentParticipant {
  id: number;
  status: ParticipantStatus;
  seed: number | null;
  points: number;
  matches_won: number;
  matches_lost: number;
}

export interface TournamentListItem {
  id: number;
  name: string;
  description: string;
  tournament_type: TournamentType;
  match_format: TournamentFormat;
  status: TournamentStatus;
  start_date: string;
  end_date: string;
  registration_deadline: string | null;
  facility: TournamentFacility | null;
  rank: number;
  max_participants: number;
  participant_count: number;
  is_participant: boolean;
  user_participant: TournamentParticipant | null;
  winner: TournamentWinner | null;
}

export interface TournamentsListResponse {
  tournaments: TournamentListItem[];
  count: number;
}

export interface ParticipantDetail {
  id: number;
  user_id: number;
  display_name: string;
  seed: number | null;
  status: ParticipantStatus;
  points: number;
  matches_won: number;
  matches_lost: number;
  sets_won: number;
  sets_lost: number;
  partner: {
    id: number;
    username: string;
    full_name: string;
  } | null;
}

export interface TournamentMatchSet {
  p1: number;
  p2: number;
}

export interface TournamentMatchDetail {
  id: number;
  round_number: number;
  match_number: number;
  status: TournamentMatchStatus;
  scheduled_time: string | null;
  participant1: {
    id: number;
    display_name: string;
  } | null;
  participant2: {
    id: number;
    display_name: string;
  } | null;
  sets: TournamentMatchSet[];
  winner: {
    id: number;
    display_name: string;
  } | null;
  court: {
    id: number;
    name: string;
    surface: string;
  } | null;
}

export interface TournamentConfig {
  sets_to_win: number;
  games_per_set: number;
  points_for_match_win: number;
  points_for_match_loss: number;
  points_for_set_win: number;
  use_seeding: boolean;
  third_place_match: boolean;
}

export interface TournamentDetail {
  id: number;
  name: string;
  description: string;
  tournament_type: TournamentType;
  match_format: TournamentFormat;
  status: TournamentStatus;
  start_date: string;
  end_date: string;
  registration_deadline: string | null;
  facility: TournamentFacility | null;
  rank: number;
  max_participants: number;
  participant_count: number;
  is_participant: boolean;
  user_participant: TournamentParticipant | null;
  winner: TournamentWinner | null;
  participants: ParticipantDetail[];
  matches: TournamentMatchDetail[];
  config: TournamentConfig | null;
  created_by: {
    id: number;
    username: string;
  };
}

export interface RegisterForTournamentPayload {
  partner_id?: number;
}

export type TiebreakerCriteria = 'head_to_head' | 'game_difference' | 'set_difference';

export interface CreateTournamentPayload {
  name: string;
  description: string;
  tournament_type: TournamentType;
  match_format: TournamentFormat;
  visibility: TournamentVisibility;
  registration_mode: RegistrationMode;
  start_date: string;
  end_date: string;
  registration_deadline: string;
  min_participants: number;
  max_participants: number;
  facility_id: number;
  rank: number;
  sets_to_win?: number;
  games_per_set?: number;
  use_seeding?: boolean;
  third_place_match?: boolean;
  // Liga scoring
  points_for_match_win?: number;
  points_for_match_loss?: number;
  points_for_set_win?: number;
  points_for_set_loss?: number;
  points_for_game_win?: number;
  points_for_game_loss?: number;
  points_for_tiebreak_point_win?: number;
  points_for_tiebreak_point_loss?: number;
  tiebreaker_criteria?: TiebreakerCriteria;
}

export interface ReportMatchResultPayload {
  set1_p1: number;
  set1_p2: number;
  set2_p1: number;
  set2_p2: number;
  set3_p1?: number;
  set3_p2?: number;
}

export interface BracketMatch {
  id: number;
  round: number;
  position: number;
  player1: string | null;
  player2: string | null;
  winner: string | null;
  status: TournamentMatchStatus;
  sets: TournamentMatchSet[];
}

export interface BracketResponse {
  bracket: BracketMatch[];
}
