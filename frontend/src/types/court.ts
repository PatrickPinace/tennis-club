/**
 * Court types
 */

export interface Court {
  id: number;
  facility_id: number;
  name: string;
  surface: string;
  is_active: boolean;
}
