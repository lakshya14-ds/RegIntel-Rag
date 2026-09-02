/**
 * Date formatting helpers for RegIntel.
 */

export function formatDate(dateStr?: string | null): string {
  if (!dateStr || dateStr === 'N/A' || dateStr === 'None' || dateStr === '1970-01-01' || dateStr === '9999-99-99') {
    return 'N/A';
  }

  try {
    // If date has timestamp
    const cleanStr = dateStr.split('T')[0];
    const parts = cleanStr.split('-');
    if (parts.length === 3) {
      const year = parseInt(parts[0], 10);
      const month = parseInt(parts[1], 10) - 1;
      const day = parseInt(parts[2], 10);
      const d = new Date(year, month, day);
      if (!isNaN(d.getTime())) {
        return d.toLocaleDateString('en-US', {
          year: 'numeric',
          month: 'short',
          day: 'numeric',
        });
      }
    }
    return cleanStr;
  } catch {
    return dateStr;
  }
}

export function formatRelativeDate(dateStr?: string | null): string {
  if (!dateStr) return 'N/A';
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return formatDate(dateStr);
    const now = new Date();
    const diffDays = Math.floor((now.getTime() - d.getTime()) / (1000 * 60 * 60 * 24));
    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays > 0 && diffDays < 30) return `${diffDays} days ago`;
    return formatDate(dateStr);
  } catch {
    return formatDate(dateStr);
  }
}
