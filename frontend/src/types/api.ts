/**
 * API types
 */

export interface ApiError {
  status: number;
  body: any;
}

export interface ApiResponse<T> {
  data?: T;
  error?: ApiError;
}
