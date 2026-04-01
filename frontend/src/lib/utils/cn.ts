/**
 * Utility function for merging class names
 * Simple implementation without clsx dependency
 */
export function cn(...classes: (string | undefined | null | false)[]): string {
  return classes.filter(Boolean).join(' ');
}
