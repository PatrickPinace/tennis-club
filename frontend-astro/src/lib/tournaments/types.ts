// Shared types for tournament client-side modules.
// These mirror the API response shapes used across all IIFEs.

export type MatchData = {
  id: number;
  round_number: number;
  match_index: number;
  bracket_type?: 'W' | 'L' | 'GF';
  status: string;
  participant1_id: number | null;
  participant2_id: number | null;
  participant3_id: number | null;
  participant4_id: number | null;
  participant1_name: string | null;
  participant2_name: string | null;
  participant3_name: string | null;
  participant4_name: string | null;
  winner_name: string | null;
  score: string | null;
  scheduled_time: string | null;
  set1_p1_score: number | null;
  set1_p2_score: number | null;
  set2_p1_score: number | null;
  set2_p2_score: number | null;
  set3_p1_score: number | null;
  set3_p2_score: number | null;
};

export type ParticipantData = {
  id: number;
  display_name: string;
  seed_number?: number | null;
  status?: string;
  user_id?: number | null;
};

export type StandingsRowRR = {
  position: number;
  display_name: string;
  points: number;
  matches_played: number;
  wins: number;
  losses: number;
  win_rate: number | null;
  sets_won: number;
  sets_lost: number;
};

export type StandingsRowAMR = {
  participant_id: number;
  display_name: string;
  points: number;
  matches_played: number;
};

export type BracketRound = {
  round: number;
  round_label: string;
  matches: BracketMatch[];
};

export type BracketMatch = {
  id: number;
  match_index: number;
  bracket_type?: 'W' | 'L' | 'GF';
  status: string;
  status_display: string;
  is_bye: boolean;
  is_third_place: boolean;
  participant1: { id: number; display_name: string; seed_number: number | null; user_id: number | null } | null;
  participant2: { id: number; display_name: string; seed_number: number | null; user_id: number | null } | null;
  winner_id: number | null;
  score: string | null;
  scheduled_time: string | null;
};

/** DBE bracket API response (distinct from SGL flat list). */
export type DBEBracketData = {
  type: 'dbe';
  winners: BracketRound[];
  losers: BracketRound[];
  grand_final: BracketRound | null;
};

export type UserItem = {
  id: number;
  first_name: string;
  last_name: string;
  username: string;
};

/** Shared organizer panel config passed from the main entry point to sub-modules. */
export type OrgPanelConfig = {
  panel: HTMLElement;
  tournamentId: string;
  createdBy: string;
  tStatus: string;
  tType: string;
  setsToWin: number;
  pointsPerMatch: number;
  apiBase: string;
  isSGL: boolean;
  isDBE: boolean;
  isAMR: boolean;
  locked: boolean;
  lockedHard: boolean;
};
