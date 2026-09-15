import React, { useState } from 'react';
import {
  AlertTriangle,
  Info,
  Calendar,
  Clock,
  ChevronDown,
  ChevronUp,
  CheckCircle,
  XCircle,
  ShieldAlert,
} from 'lucide-react';
import { RegulatoryAlert, AlertSeverity } from '../../types/api';

interface AlertCardProps {
  alert: RegulatoryAlert;
  onMarkRead?: (alertId: string) => void;
  onDismiss?: (alertId: string) => void;
}

export const AlertCard: React.FC<AlertCardProps> = ({ alert, onMarkRead, onDismiss }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const getSeverityStyle = (sev: AlertSeverity) => {
    switch (sev) {
      case 'CRITICAL':
        return {
          badge: 'bg-red-500/20 text-red-400 border-red-500/30',
          border: 'border-l-red-500',
          icon: <ShieldAlert className="w-5 h-5 text-red-400" />,
        };
      case 'HIGH':
        return {
          badge: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
          border: 'border-l-orange-500',
          icon: <AlertTriangle className="w-5 h-5 text-orange-400" />,
        };
      case 'MEDIUM':
        return {
          badge: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
          border: 'border-l-amber-500',
          icon: <Clock className="w-5 h-5 text-amber-400" />,
        };
      case 'LOW':
      case 'INFO':
      default:
        return {
          badge: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
          border: 'border-l-blue-500',
          icon: <Info className="w-5 h-5 text-blue-400" />,
        };
    }
  };

  const style = getSeverityStyle(alert.severity);

  return (
    <div
      className={`bg-slate-900/90 border border-slate-800 rounded-xl p-5 border-l-4 ${style.border} transition-all duration-200 hover:border-slate-700 shadow-md`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="mt-0.5">{style.icon}</div>
          <div>
            <div className="flex items-center gap-2 flex-wrap mb-1">
              <span className={`text-xs font-semibold px-2.5 py-0.5 rounded-full border ${style.badge}`}>
                {alert.severity}
              </span>
              <span className="text-xs font-mono text-slate-400 bg-slate-800/80 px-2 py-0.5 rounded">
                {alert.alert_type.replace(/_/g, ' ')}
              </span>
              {alert.status === 'READ' && (
                <span className="text-xs text-emerald-400 bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-800/40">
                  READ
                </span>
              )}
            </div>
            <h4 className="text-base font-medium text-slate-100">{alert.title}</h4>
            <p className="text-sm text-slate-300 mt-1">{alert.message}</p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {alert.status !== 'READ' && onMarkRead && (
            <button
              onClick={() => onMarkRead(alert.alert_id)}
              className="p-1.5 text-slate-400 hover:text-emerald-400 hover:bg-slate-800 rounded-lg transition-colors"
              title="Mark as Read"
            >
              <CheckCircle className="w-4 h-4" />
            </button>
          )}
          {onDismiss && (
            <button
              onClick={() => onDismiss(alert.alert_id)}
              className="p-1.5 text-slate-400 hover:text-red-400 hover:bg-slate-800 rounded-lg transition-colors"
              title="Dismiss Alert"
            >
              <XCircle className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      <div className="flex items-center justify-between mt-4 pt-3 border-t border-slate-800/60 text-xs text-slate-400">
        <div className="flex items-center gap-4 flex-wrap">
          {alert.effective_date && (
            <span className="flex items-center gap-1.5">
              <Calendar className="w-3.5 h-3.5 text-slate-500" />
              Effective: <strong className="text-slate-300">{alert.effective_date}</strong>
            </span>
          )}
          {alert.deadline && (
            <span className="flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-slate-500" />
              Deadline: <strong className="text-slate-300">{alert.deadline}</strong>
            </span>
          )}
          {alert.document_id && (
            <span className="font-mono text-slate-400">Doc: {alert.document_id}</span>
          )}
        </div>

        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex items-center gap-1 text-sky-400 hover:text-sky-300 font-medium py-1 px-2 rounded hover:bg-slate-800/50 transition-colors"
        >
          {isExpanded ? (
            <>
              Hide Explainability <ChevronUp className="w-3.5 h-3.5" />
            </>
          ) : (
            <>
              Why am I seeing this? <ChevronDown className="w-3.5 h-3.5" />
            </>
          )}
        </button>
      </div>

      {isExpanded && alert.explanation && (
        <div className="mt-4 p-4 bg-slate-950/70 border border-slate-800 rounded-lg space-y-3 text-xs">
          <div>
            <span className="text-slate-400 font-medium block mb-0.5">Why am I seeing this?</span>
            <p className="text-slate-200">{alert.explanation.why_am_i_seeing_this}</p>
          </div>

          {alert.explanation.what_changed && (
            <div>
              <span className="text-slate-400 font-medium block mb-0.5">What changed?</span>
              <p className="text-slate-200">{alert.explanation.what_changed}</p>
            </div>
          )}

          {alert.explanation.action_recommended && (
            <div className="bg-sky-950/30 border border-sky-900/40 p-2.5 rounded text-sky-200">
              <span className="font-semibold block mb-0.5">Recommended Action:</span>
              <p>{alert.explanation.action_recommended}</p>
            </div>
          )}

          {alert.explanation.source && (
            <div className="pt-2 border-t border-slate-800/60 flex items-center justify-between text-slate-400">
              <span>Source Evidence: <em className="text-slate-300">"{alert.explanation.source}"</em></span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
