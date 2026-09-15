import React, { useState, useEffect } from 'react';
import {
  Calendar as CalendarIcon,
  Filter,
  Clock,
} from 'lucide-react';
import { RegulatoryDateEvent } from '../../types/api';
import { fetchRegulatoryCalendar } from '../../api/compliance';

export const RegulatoryCalendarView: React.FC = () => {
  const [events, setEvents] = useState<RegulatoryDateEvent[]>([]);
  const [eventTypeFilter, setEventTypeFilter] = useState<string>('ALL');
  const [isLoading, setIsLoading] = useState(false);

  const loadCalendar = () => {
    setIsLoading(true);
    const filter = eventTypeFilter === 'ALL' ? undefined : eventTypeFilter;
    fetchRegulatoryCalendar(undefined, undefined, filter)
      .then(setEvents)
      .catch((err) => console.error('Failed to load calendar events:', err))
      .finally(() => setIsLoading(false));
  };

  useEffect(() => {
    loadCalendar();
  }, [eventTypeFilter]);

  const getEventBadge = (type: string) => {
    switch (type) {
      case 'EFFECTIVE':
        return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
      case 'PUBLISHED':
        return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
      case 'EXPIRES':
        return 'bg-red-500/20 text-red-400 border-red-500/30';
      case 'DEADLINE':
        return 'bg-amber-500/20 text-amber-400 border-amber-500/30';
      default:
        return 'bg-slate-700/40 text-slate-300 border-slate-600/40';
    }
  };

  return (
    <div className="space-y-4">
      {/* Controls Bar */}
      <div className="flex items-center justify-between gap-4 p-4 bg-slate-900/80 border border-slate-800 rounded-xl">
        <div className="flex items-center gap-2 text-slate-200 font-medium">
          <CalendarIcon className="w-5 h-5 text-sky-400" />
          <span>Regulatory Intelligence Timeline & Calendar</span>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs text-slate-400">
            <Filter className="w-3.5 h-3.5" />
            <span>Event Type:</span>
          </div>
          <select
            value={eventTypeFilter}
            onChange={(e) => setEventTypeFilter(e.target.value)}
            className="bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg px-3 py-1.5 focus:outline-none focus:border-sky-500"
          >
            <option value="ALL">All Event Types</option>
            <option value="EFFECTIVE">Effective Dates</option>
            <option value="PUBLISHED">Publication Dates</option>
            <option value="EXPIRES">Expiry / Sunset Dates</option>
            <option value="DEADLINE">Compliance Deadlines</option>
          </select>
        </div>
      </div>

      {/* Events List */}
      {isLoading ? (
        <div className="p-8 text-center text-slate-400 text-sm">Loading regulatory calendar events...</div>
      ) : events.length === 0 ? (
        <div className="p-12 text-center bg-slate-900/40 border border-slate-800 rounded-xl">
          <Clock className="w-8 h-8 text-slate-600 mx-auto mb-2" />
          <p className="text-slate-400 text-sm">No regulatory events found for the selected filter.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {events.map((ev) => (
            <div
              key={ev.event_id}
              className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:border-slate-700 transition-colors"
            >
              <div className="flex items-start gap-3">
                <div className="bg-slate-800/80 border border-slate-700/60 rounded-lg p-2.5 text-center min-w-[85px] shrink-0">
                  <span className="text-xs font-mono text-slate-400 block">
                    {ev.date ? ev.date.slice(0, 7) : 'Pending'}
                  </span>
                  <span className="text-base font-bold text-slate-100 block">
                    {ev.date ? ev.date.slice(8, 10) : '—'}
                  </span>
                </div>

                <div>
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <span className={`text-xs font-semibold px-2.5 py-0.5 rounded-full border ${getEventBadge(ev.event_type)}`}>
                      {ev.event_type}
                    </span>
                    <span className="text-xs text-slate-400 font-mono bg-slate-800 px-2 py-0.5 rounded">
                      Doc: {ev.document_id}
                    </span>
                    <span className="text-xs text-slate-500">
                      Derivation: <strong className="text-slate-400">{ev.derivation_type}</strong>
                    </span>
                  </div>

                  <p className="text-sm text-slate-200 mt-1 italic">
                    "{ev.source_text}"
                  </p>

                  {ev.derivation_rule && (
                    <span className="text-xs text-slate-400 block mt-1">
                      Rule: {ev.derivation_rule}
                    </span>
                  )}
                </div>
              </div>

              <div className="text-right shrink-0">
                <span className="text-xs font-mono text-slate-500 block">
                  Confidence: {ev.confidence}
                </span>
                <span className="text-xs text-slate-500">
                  Method: {ev.extraction_method}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
