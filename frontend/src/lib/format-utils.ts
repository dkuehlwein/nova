/**
 * Utility functions for formatting dates and timestamps
 * Used primarily in chat components for German locale display
 */

/**
 * Format timestamp in German local time with date and time
 * @param timestamp - ISO timestamp string
 * @returns Formatted string like "09.01.26, 14:30"
 */
export function formatTimestamp(timestamp: string): string {
  if (!timestamp) return '';
  try {
    return new Date(timestamp).toLocaleString('de-DE', {
      timeZone: 'Europe/Berlin',
      hour: '2-digit',
      minute: '2-digit',
      day: '2-digit',
      month: '2-digit',
      year: '2-digit',
    });
  } catch {
    return timestamp;
  }
}

/**
 * Format date in German local time with weekday
 * @param timestamp - ISO timestamp string
 * @returns Formatted string like "Do., 09.01.26"
 */
export function formatDate(timestamp: string): string {
  if (!timestamp) return '';
  try {
    return new Date(timestamp).toLocaleDateString('de-DE', {
      timeZone: 'Europe/Berlin',
      weekday: 'short',
      day: '2-digit',
      month: '2-digit',
      year: '2-digit',
    });
  } catch {
    return timestamp;
  }
}
