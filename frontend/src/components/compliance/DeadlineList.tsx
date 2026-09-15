import React, { useState, useEffect } from 'react';
import {
  Clock,
  CheckCircle2,
  Repeat,
  Filter,
} from 'lucide-react';
import { RegulatoryDeadline } from '../../types/api';
import { fetchDeadlines } from '../../api/compliance';

export const DeadlineList: React.FC = () => {
  const [deadlines, setDeadlines] = useState<RegulatoryDeadline[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    setIsLoading(true);
    const filter = statusFilter === 'ALL' ? undefined : statusFilter;
    fetchDeadlines({ status: filter, limit: 100 })
      .then(setDeadlines)
      .catch((err) => console.error('Failed to load deadlines:', err))
      .finally(() => setIsLoading(false));
  }, [statusFilter]);

  const getStatusBadge = (status: string, days?: number | null) => {
    switch (status) {
      case 'OVERDUE':
        return {
          badge: 'bg-red-500/20 text-red-400 border-red-500/30',
          text: days !== undefined && days !== null ? `${Math.abs(days)}d OVERDUE` : 'OVERDUE',
        };
      case 'DUE_TODAY':
        return {
          badge: 'bg-red-500/20 text-red-400 border-red-500/30',
          text: 'DUE TODAY',
        };
      case 'DUE_SOON':
        return {
          badge: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
          text: days !== undefined && days !== null ? `Due in ${days}d` : 'DUE SOON',
        };
      case 'UPCOMING':
      default:
        return {
          badge: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
          text: days !== undefined && days !== null ? `In ${days}d` : 'UPCOMING',
        };
    }
  };

  return (
    <div className="space-y-4">
      {/* Controls Bar */}
      <div className="flex items-center justify-between gap-4 p-4 bg-slate-900/80 border border-slate-800 rounded-xl">
        <div className="flex items-center gap-2 text-slate-200 font-medium">
          <Clock className="w-5 h-5 text-amber-400" />
          <span>Compliance Deadlines & Reporting Schedules</span>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs text-slate-400">
            <Filter className="w-3.5 h-3.5" />
            <span>Filter Status:</span>
          </div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg px-3 py-1.5 focus:outline-none focus:border-sky-500"
          >
            <option value="ALL">All Deadlines</option>
            <option value="DUE_SOON">Due Soon (≤7 days)</option>
            <option value="UPCOMING">Upcoming</option>
            <option value="OVERDUE">Overdue</option>
          </select>
        </div>
      </div>

      {/* Deadlines List */}
      {isLoading ? (
        <div className="p-8 text-center text-slate-400 text-sm">Loading compliance deadlines...</div>
      ) : deadlines.length === 0 ? (
        <div className="p-12 text-center bg-slate-900/40 border border-slate-800 rounded-xl">
          <CheckCircle2 className="w-8 h-8 text-slate-600 mx-auto mb-2" />
          <p className="text-slate-400 text-sm">No deadlines matching the current filter.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {deadlines.map((ddl) => {
            const statusInfo = getStatusBadge(ddl.status, ddl.days_remaining);
            return (
              <div
                key={ddl.deadline_id}
                className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition-colors"
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2 flex-wrap mb-1.5">
                      <span className={`text-xs font-semibold px-2.5 py-0.5 rounded-full border ${statusInfo.badge}`}>
                        {statusInfo.text}
                      </span>
                      {ddl.frequency && (
                        <span className="flex items-center gap-1 text-xs text-sky-400 bg-sky-950/40 border border-sky-800/40 px-2 py-0.5 rounded">
                          <Repeat className="w-3 h-3" />
                          {ddl.frequency}
                        </span>
                      )}
                      <span className="text-xs font-mono text-slate-400 bg-slate-800 px-2 py-0.5 rounded">
                        Doc: {ddl.document_id}
                      </span>
                    </div>

                    <h4 className="text-base font-medium text-slate-100">
                      {ddl.trigger_event ? `${ddl.trigger_event} — ` : ''}
                      {ddl.deadline_expression}
                    </h4>

                    <p className="text-xs text-slate-400 mt-1.5 italic">
                      Source: "{ddl.source_evidence}"
                    </p>
                  </div>

                  <div className="text-right shrink-0">
                    <span className="text-xs text-slate-500 block">Due Date</span>
                    <span className="text-sm font-semibold text-slate-200">
                      {ddl.due_date || 'Pending'}
                    </span>
                    <span className="text-xs text-slate-500 block mt-0.5">
                      {ddl.due_date_derivation}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
