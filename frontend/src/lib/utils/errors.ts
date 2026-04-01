/**
 * Error handling utilities
 */

export function getReservationErrorMessage(error: any): string {
  if (error?.status === 409) {
    return 'Wybrany termin został właśnie zajęty.';
  }
  if (error?.status === 401 || error?.status === 403) {
    return 'Sesja wygasła. Zaloguj się ponownie.';
  }
  if (error?.status === 400) {
    return error?.body?.message || 'Nieprawidłowe dane formularza.';
  }
  return 'Wystąpił błąd podczas tworzenia rezerwacji.';
}
