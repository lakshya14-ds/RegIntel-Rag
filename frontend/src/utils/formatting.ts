/**
 * Formatting and Badge Helpers for RegIntel UI.
 */

export function truncateText(text: string, maxLength: number): string {
  if (!text || text.length <= maxLength) return text;
  return `${text.slice(0, maxLength).trim()}...`;
}

export function formatScore(score: number): string {
  if (typeof score !== 'number' || isNaN(score)) return '0.00';
  return score.toFixed(4);
}

export function formatPercent(val: number): string {
  if (typeof val !== 'number' || isNaN(val)) return '0%';
  return `${(val * 100).toFixed(1)}%`;
}

export function getStatusColor(status?: string | null): { bg: string; text: string; border: string } {
  const s = (status || 'unknown').toLowerCase();
  if (s === 'current' || s === 'active') {
    return { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200' };
  }
  if (s === 'historical' || s === 'superseded') {
    return { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200' };
  }
  return { bg: 'bg-slate-100', text: 'text-slate-700', border: 'border-slate-200' };
}

export function getChangeTypeColor(changeType: string): { bg: string; text: string; border: string; label: string } {
  const c = changeType.toUpperCase();
  switch (c) {
    case 'ADDED':
      return { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200', label: 'ADDED' };
    case 'REMOVED':
      return { bg: 'bg-rose-50', text: 'text-rose-700', border: 'border-rose-200', label: 'REMOVED' };
    case 'MODIFIED':
      return { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200', label: 'MODIFIED' };
    case 'UNCHANGED':
      return { bg: 'bg-slate-50', text: 'text-slate-600', border: 'border-slate-200', label: 'UNCHANGED' };
    default:
      return { bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200', label: c };
  }
}

export function getConfidenceColor(confidence?: string | null): { bg: string; text: string; border: string } {
  const c = (confidence || 'unknown').toUpperCase();
  if (c === 'HIGH') {
    return { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200' };
  }
  if (c === 'MEDIUM') {
    return { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200' };
  }
  if (c === 'LOW') {
    return { bg: 'bg-rose-50', text: 'text-rose-700', border: 'border-rose-200' };
  }
  return { bg: 'bg-slate-100', text: 'text-slate-600', border: 'border-slate-200' };
}
