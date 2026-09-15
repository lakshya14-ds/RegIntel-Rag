import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import {
  ClipboardCheck,
  PlusCircle,
  AlertTriangle,
  FileText,
  Bell,
  Clock,
  Calendar as CalendarIcon,
  Eye,
  Play,
  CheckCircle2,
} from 'lucide-react';
import {
  ComplianceChecklist,
  ChecklistItem,
  ChecklistStatus,
  RegulatoryRequirement,
  RegulatoryObligation,
  RegulatoryAlert,
  Watchlist,
} from '../types/api';
import {
  fetchChecklists,
  fetchChecklist,
  generateChecklist,
  updateChecklistItem,
  regenerateChecklist,
  exportChecklist,
  fetchRequirements,
  fetchObligations,
  fetchAlerts,
  markAlertRead,
  dismissAlert,
  fetchWatchlists,
  triggerAlertEvaluation,
} from '../api/compliance';
import { ChecklistProgressDashboard } from '../components/compliance/ChecklistProgressDashboard';
import { EvidenceDrawer } from '../components/compliance/EvidenceDrawer';
import { RequirementCard } from '../components/compliance/RequirementCard';
import { ObligationCard } from '../components/compliance/ObligationCard';
import { AlertCard } from '../components/compliance/AlertCard';
import { RegulatoryCalendarView } from '../components/compliance/RegulatoryCalendarView';
import { DeadlineList } from '../components/compliance/DeadlineList';
import { WatchlistModal } from '../components/compliance/WatchlistModal';

type TabType = 'alerts' | 'deadlines' | 'calendar' | 'checklists' | 'requirements' | 'obligations';

export const Compliance: React.FC = () => {
  const { checklistId } = useParams<{ checklistId?: string }>();

  // Tab State
  const [activeTab, setActiveTab] = useState<TabType>('alerts');

  // Checklists State
  const [checklists, setChecklists] = useState<ComplianceChecklist[]>([]);
  const [currentChecklist, setCurrentChecklist] = useState<ComplianceChecklist | null>(null);
  const [selectedItemForEvidence, setSelectedItemForEvidence] = useState<ChecklistItem | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [isLoading, setIsLoading] = useState(false);
  const [isRegenerating, setIsRegenerating] = useState(false);

  // Alerts State (Phase 65)
  const [alerts, setAlerts] = useState<RegulatoryAlert[]>([]);
  const [alertSeverityFilter, setAlertSeverityFilter] = useState<string>('ALL');
  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);
  const [showWatchlistModal, setShowWatchlistModal] = useState(false);
  const [isEvaluating, setIsEvaluating] = useState(false);

  // New Checklist Modal State
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newTitle, setNewTitle] = useState('SEBI Comprehensive Compliance Checklist');
  const [newAuthority, setNewAuthority] = useState('SEBI');
  const [newEntityFilter, setNewEntityFilter] = useState('Investment Adviser');
  const [isCreating, setIsCreating] = useState(false);

  // Requirements & Obligations Explorer State
  const [explorerReqs, setExplorerReqs] = useState<RegulatoryRequirement[]>([]);
  const [explorerObs, setExplorerObs] = useState<RegulatoryObligation[]>([]);

  // Load Alerts & Watchlists
  const loadAlerts = () => {
    fetchAlerts({ limit: 100 })
      .then(setAlerts)
      .catch((err) => console.error('Error fetching alerts:', err));
  };

  const loadWatchlistsData = () => {
    fetchWatchlists()
      .then(setWatchlists)
      .catch((err) => console.error('Error fetching watchlists:', err));
  };

  useEffect(() => {
    loadAlerts();
    loadWatchlistsData();
  }, []);

  // Load Checklists List
  useEffect(() => {
    fetchChecklists()
      .then((data) => {
        setChecklists(data);
        if (checklistId) {
          const target = data.find((c) => c.checklist_id === checklistId);
          if (target) {
            setCurrentChecklist(target);
            setActiveTab('checklists');
          } else {
            loadChecklistDetail(checklistId);
            setActiveTab('checklists');
          }
        } else if (data.length > 0 && !currentChecklist) {
          setCurrentChecklist(data[0]);
        }
      })
      .catch((err) => console.error('Error fetching checklists:', err));
  }, [checklistId]);

  const loadChecklistDetail = (id: string) => {
    setIsLoading(true);
    fetchChecklist(id)
      .then((chk) => setCurrentChecklist(chk))
      .catch((err) => console.error('Error loading checklist detail:', err))
      .finally(() => setIsLoading(false));
  };

  // Load Requirements/Obligations on tab switch
  useEffect(() => {
    if (activeTab === 'requirements' && explorerReqs.length === 0) {
      fetchRequirements({ limit: 50 }).then(setExplorerReqs).catch(console.error);
    } else if (activeTab === 'obligations' && explorerObs.length === 0) {
      fetchObligations({ limit: 50 }).then(setExplorerObs).catch(console.error);
    }
  }, [activeTab]);

  const handleMarkAlertRead = async (alertId: string) => {
    try {
      const updated = await markAlertRead(alertId);
      setAlerts((prev) => prev.map((a) => (a.alert_id === updated.alert_id ? updated : a)));
    } catch (err) {
      console.error('Failed to mark read:', err);
    }
  };

  const handleDismissAlert = async (alertId: string) => {
    try {
      await dismissAlert(alertId);
      setAlerts((prev) => prev.filter((a) => a.alert_id !== alertId));
    } catch (err) {
      console.error('Failed to dismiss alert:', err);
    }
  };

  const handleTriggerEvaluation = async () => {
    setIsEvaluating(true);
    try {
      await triggerAlertEvaluation();
      loadAlerts();
    } catch (err) {
      console.error('Failed to evaluate alerts:', err);
    } finally {
      setIsEvaluating(false);
    }
  };

  const handleStatusChange = async (itemId: string, newStatus: ChecklistStatus) => {
    if (!currentChecklist) return;
    try {
      const updated = await updateChecklistItem(currentChecklist.checklist_id, itemId, { status: newStatus });
      setCurrentChecklist(updated);
      setChecklists((prev) => prev.map((c) => (c.checklist_id === updated.checklist_id ? updated : c)));
    } catch (err) {
      console.error('Failed to update status:', err);
    }
  };

  const handleNotesChange = async (itemId: string, notes: string) => {
    if (!currentChecklist) return;
    try {
      const updated = await updateChecklistItem(currentChecklist.checklist_id, itemId, { notes });
      setCurrentChecklist(updated);
    } catch (err) {
      console.error('Failed to save notes:', err);
    }
  };

  const handleRegenerate = async () => {
    if (!currentChecklist) return;
    setIsRegenerating(true);
    try {
      const regenerated = await regenerateChecklist(currentChecklist.checklist_id);
      setCurrentChecklist(regenerated);
      setChecklists((prev) => prev.map((c) => (c.checklist_id === regenerated.checklist_id ? regenerated : c)));
    } catch (err) {
      console.error('Regeneration error:', err);
    } finally {
      setIsRegenerating(false);
    }
  };

  const handleExport = async (format: 'markdown' | 'json') => {
    if (!currentChecklist) return;
    try {
      const content = await exportChecklist(currentChecklist.checklist_id, format);
      const blob = new Blob([content], { type: format === 'json' ? 'application/json' : 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${currentChecklist.checklist_id}.${format === 'json' ? 'json' : 'md'}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Export error:', err);
    }
  };

  const handleCreateChecklist = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsCreating(true);
    try {
      const created = await generateChecklist({
        title: newTitle,
        authority: newAuthority,
        entity_filter: newEntityFilter,
      });
      setChecklists([created, ...checklists]);
      setCurrentChecklist(created);
      setShowCreateModal(false);
    } catch (err: any) {
      alert(err.message || 'Error generating checklist');
    } finally {
      setIsCreating(false);
    }
  };

  // Filter items
  const filteredItems = currentChecklist
    ? currentChecklist.items.filter((item) => {
        if (statusFilter === 'ALL') return true;
        return item.status === statusFilter;
      })
    : [];

  const unreadAlerts = alerts.filter((a) => a.status === 'UNREAD');
  const filteredAlerts = alerts.filter((a) => {
    if (alertSeverityFilter === 'ALL') return true;
    return a.severity === alertSeverityFilter;
  });

  return (
    <div className="page-container">
      {/* Top Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 800, color: '#0f172a', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ClipboardCheck size={28} style={{ color: '#2563eb' }} />
            Regulatory Intelligence, Alerts & Compliance
          </h1>
          <p style={{ color: '#64748b', fontSize: '0.88rem', margin: '4px 0 0 0' }}>
            Event-driven regulatory intelligence: track effective dates, compliance deadlines, deduplicated alerts, and audited checklists.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button
            onClick={() => setShowWatchlistModal(true)}
            className="btn btn-secondary"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
          >
            <Eye size={15} /> Watchlists ({watchlists.length})
          </button>
          <button
            onClick={handleTriggerEvaluation}
            className="btn btn-secondary"
            disabled={isEvaluating}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
          >
            <Play size={15} /> {isEvaluating ? 'Evaluating...' : 'Run Intelligence Evaluation'}
          </button>
          <button
            onClick={() => setShowCreateModal(true)}
            className="btn btn-primary"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
          >
            <PlusCircle size={16} /> Generate Checklist
          </button>
        </div>
      </div>

      {/* Unread Alert Notification Banner */}
      {unreadAlerts.length > 0 && activeTab !== 'alerts' && (
        <div
          onClick={() => setActiveTab('alerts')}
          className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-3.5 mb-6 flex items-center justify-between cursor-pointer hover:bg-amber-500/15 transition-colors"
        >
          <div className="flex items-center gap-3">
            <Bell className="w-5 h-5 text-amber-400 shrink-0" />
            <div>
              <span className="text-sm font-semibold text-amber-200">
                {unreadAlerts.length} Regulatory Alert{unreadAlerts.length > 1 ? 's' : ''} Require Attention
              </span>
              <p className="text-xs text-amber-300/80">
                Click to view upcoming effective dates, deadline alerts, and modified obligations.
              </p>
            </div>
          </div>
          <span className="text-xs font-semibold text-amber-400 bg-amber-950/60 px-3 py-1 rounded-full border border-amber-700/50">
            View Alerts →
          </span>
        </div>
      )}

      {/* Navigation Tabs */}
      <div style={{ display: 'flex', gap: '0.5rem', borderBottom: '2px solid #e2e8f0', marginBottom: '1.5rem', overflowX: 'auto' }}>
        <button
          className={`tab-button ${activeTab === 'alerts' ? 'active' : ''}`}
          onClick={() => setActiveTab('alerts')}
          style={{
            padding: '0.6rem 1.2rem',
            border: 'none',
            background: 'none',
            fontWeight: 700,
            fontSize: '0.92rem',
            color: activeTab === 'alerts' ? '#2563eb' : '#64748b',
            borderBottom: activeTab === 'alerts' ? '3px solid #2563eb' : 'none',
            cursor: 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            whiteSpace: 'nowrap',
          }}
        >
          <Bell size={16} />
          Alerts {unreadAlerts.length > 0 && `(${unreadAlerts.length})`}
        </button>

        <button
          className={`tab-button ${activeTab === 'deadlines' ? 'active' : ''}`}
          onClick={() => setActiveTab('deadlines')}
          style={{
            padding: '0.6rem 1.2rem',
            border: 'none',
            background: 'none',
            fontWeight: 700,
            fontSize: '0.92rem',
            color: activeTab === 'deadlines' ? '#2563eb' : '#64748b',
            borderBottom: activeTab === 'deadlines' ? '3px solid #2563eb' : 'none',
            cursor: 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            whiteSpace: 'nowrap',
          }}
        >
          <Clock size={16} />
          Deadlines & Schedules
        </button>

        <button
          className={`tab-button ${activeTab === 'calendar' ? 'active' : ''}`}
          onClick={() => setActiveTab('calendar')}
          style={{
            padding: '0.6rem 1.2rem',
            border: 'none',
            background: 'none',
            fontWeight: 700,
            fontSize: '0.92rem',
            color: activeTab === 'calendar' ? '#2563eb' : '#64748b',
            borderBottom: activeTab === 'calendar' ? '3px solid #2563eb' : 'none',
            cursor: 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            whiteSpace: 'nowrap',
          }}
        >
          <CalendarIcon size={16} />
          Calendar & Timeline
        </button>

        <button
          className={`tab-button ${activeTab === 'checklists' ? 'active' : ''}`}
          onClick={() => setActiveTab('checklists')}
          style={{
            padding: '0.6rem 1.2rem',
            border: 'none',
            background: 'none',
            fontWeight: 700,
            fontSize: '0.92rem',
            color: activeTab === 'checklists' ? '#2563eb' : '#64748b',
            borderBottom: activeTab === 'checklists' ? '3px solid #2563eb' : 'none',
            cursor: 'pointer',
            whiteSpace: 'nowrap',
          }}
        >
          Compliance Checklists ({checklists.length})
        </button>

        <button
          className={`tab-button ${activeTab === 'requirements' ? 'active' : ''}`}
          onClick={() => setActiveTab('requirements')}
          style={{
            padding: '0.6rem 1.2rem',
            border: 'none',
            background: 'none',
            fontWeight: 700,
            fontSize: '0.92rem',
            color: activeTab === 'requirements' ? '#2563eb' : '#64748b',
            borderBottom: activeTab === 'requirements' ? '3px solid #2563eb' : 'none',
            cursor: 'pointer',
            whiteSpace: 'nowrap',
          }}
        >
          Extracted Requirements (Phase 61)
        </button>

        <button
          className={`tab-button ${activeTab === 'obligations' ? 'active' : ''}`}
          onClick={() => setActiveTab('obligations')}
          style={{
            padding: '0.6rem 1.2rem',
            border: 'none',
            background: 'none',
            fontWeight: 700,
            fontSize: '0.92rem',
            color: activeTab === 'obligations' ? '#2563eb' : '#64748b',
            borderBottom: activeTab === 'obligations' ? '3px solid #2563eb' : 'none',
            cursor: 'pointer',
            whiteSpace: 'nowrap',
          }}
        >
          Operational Obligations (Phase 62)
        </button>
      </div>

      {/* TAB 1: REGULATORY ALERTS (Phase 65) */}
      {activeTab === 'alerts' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-4 p-4 bg-slate-900/80 border border-slate-800 rounded-xl flex-wrap">
            <div className="flex items-center gap-2 text-slate-200 font-medium">
              <Bell className="w-5 h-5 text-sky-400" />
              <span>Proactive Regulatory Alerts ({alerts.length})</span>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400">Filter Severity:</span>
              {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((sev) => (
                <button
                  key={sev}
                  onClick={() => setAlertSeverityFilter(sev)}
                  className={`px-2.5 py-1 rounded-lg text-xs font-semibold border transition-colors ${
                    alertSeverityFilter === sev
                      ? 'bg-sky-600 text-white border-sky-500'
                      : 'bg-slate-800 text-slate-400 border-slate-700 hover:text-slate-200'
                  }`}
                >
                  {sev}
                </button>
              ))}
            </div>
          </div>

          {filteredAlerts.length === 0 ? (
            <div className="p-12 text-center bg-slate-900/40 border border-slate-800 rounded-xl">
              <CheckCircle2 className="w-8 h-8 text-slate-600 mx-auto mb-2" />
              <p className="text-slate-400 text-sm">No regulatory alerts matching this severity filter.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {filteredAlerts.map((alert) => (
                <AlertCard
                  key={alert.alert_id}
                  alert={alert}
                  onMarkRead={handleMarkAlertRead}
                  onDismiss={handleDismissAlert}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 2: DEADLINES & SCHEDULES (Phase 65) */}
      {activeTab === 'deadlines' && <DeadlineList />}

      {/* TAB 3: CALENDAR & TIMELINE (Phase 64) */}
      {activeTab === 'calendar' && <RegulatoryCalendarView />}

      {/* TAB 4: COMPLIANCE CHECKLISTS (Phase 63) */}
      {activeTab === 'checklists' && (
        <>
          {currentChecklist && (
            <ChecklistProgressDashboard
              checklist={currentChecklist}
              onExportMarkdown={() => handleExport('markdown')}
              onExportJson={() => handleExport('json')}
              onRegenerate={handleRegenerate}
              isRegenerating={isRegenerating}
            />
          )}

          {/* Filter Bar */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
            <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
              {['ALL', 'NOT_REVIEWED', 'COMPLIANT', 'NON_COMPLIANT', 'NEEDS_REVIEW'].map((st) => (
                <button
                  key={st}
                  onClick={() => setStatusFilter(st)}
                  className={`btn btn-sm ${statusFilter === st ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ fontSize: '0.78rem' }}
                >
                  {st.replace('_', ' ')}
                </button>
              ))}
            </div>

            {checklists.length > 1 && (
              <select
                value={currentChecklist?.checklist_id}
                onChange={(e) => {
                  const c = checklists.find((chk) => chk.checklist_id === e.target.value);
                  if (c) setCurrentChecklist(c);
                }}
                className="select select-sm"
              >
                {checklists.map((c) => (
                  <option key={c.checklist_id} value={c.checklist_id}>
                    {c.title} ({c.items.length} items)
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* Items List */}
          {isLoading ? (
            <div style={{ padding: '2rem', textAlign: 'center', color: '#64748b' }}>Loading checklist...</div>
          ) : filteredItems.length === 0 ? (
            <div style={{ padding: '3rem', textAlign: 'center', background: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
              <p style={{ color: '#64748b', fontSize: '0.92rem', margin: 0 }}>No checklist items match the selected status.</p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {filteredItems.map((item) => (
                <div
                  key={item.item_id}
                  style={{
                    background: '#ffffff',
                    border: '1px solid #e2e8f0',
                    borderRadius: '8px',
                    padding: '1.25rem',
                    boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem', marginBottom: '0.5rem' }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                        <span style={{ fontSize: '0.72rem', fontFamily: 'monospace', color: '#64748b', background: '#f1f5f9', padding: '2px 6px', borderRadius: '4px' }}>
                          {item.item_id}
                        </span>
                        {item.obligated_party && (
                          <span style={{ fontSize: '0.72rem', fontWeight: 600, color: '#1e40af', background: '#dbeafe', padding: '2px 6px', borderRadius: '4px' }}>
                            {item.obligated_party}
                          </span>
                        )}
                        {item.is_changed && (
                          <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#b45309', background: '#fef3c7', padding: '2px 6px', borderRadius: '4px', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                            <AlertTriangle size={12} /> MODIFIED IN LATEST VERSION
                          </span>
                        )}
                      </div>

                      <h4 style={{ fontSize: '1rem', fontWeight: 700, color: '#0f172a', margin: '0 0 6px 0' }}>
                        {item.control_question}
                      </h4>

                      <p style={{ fontSize: '0.85rem', color: '#334155', margin: '0 0 8px 0' }}>
                        <strong>Action Required:</strong> {item.compliance_action}
                      </p>

                      {item.evidence_required && item.evidence_required.length > 0 && (
                        <div style={{ fontSize: '0.78rem', color: '#475569', marginBottom: '8px' }}>
                          <strong>Expected Evidence:</strong> {item.evidence_required.join(', ')}
                        </div>
                      )}
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '6px' }}>
                      <select
                        value={item.status}
                        onChange={(e) => handleStatusChange(item.item_id, e.target.value as ChecklistStatus)}
                        className="select select-sm"
                        style={{
                          fontWeight: 700,
                          fontSize: '0.8rem',
                          background:
                            item.status === 'COMPLIANT'
                              ? '#dcfce7'
                              : item.status === 'NON_COMPLIANT'
                              ? '#fee2e2'
                              : item.status === 'NEEDS_REVIEW'
                              ? '#fef3c7'
                              : '#f1f5f9',
                          color:
                            item.status === 'COMPLIANT'
                              ? '#166534'
                              : item.status === 'NON_COMPLIANT'
                              ? '#991b1b'
                              : item.status === 'NEEDS_REVIEW'
                              ? '#92400e'
                              : '#475569',
                          borderColor: 'transparent',
                        }}
                      >
                        <option value="NOT_REVIEWED">NOT REVIEWED</option>
                        <option value="COMPLIANT">COMPLIANT</option>
                        <option value="PARTIALLY_COMPLIANT">PARTIALLY COMPLIANT</option>
                        <option value="NON_COMPLIANT">NON COMPLIANT</option>
                        <option value="NEEDS_REVIEW">NEEDS REVIEW</option>
                        <option value="NOT_APPLICABLE">NOT APPLICABLE</option>
                      </select>

                      <button
                        onClick={() => setSelectedItemForEvidence(item)}
                        style={{
                          background: 'none',
                          border: 'none',
                          color: '#2563eb',
                          fontSize: '0.78rem',
                          cursor: 'pointer',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          padding: '2px 4px',
                        }}
                      >
                        <FileText size={12} /> View Evidence
                      </button>
                    </div>
                  </div>

                  <div style={{ borderTop: '1px solid #f1f5f9', paddingTop: '8px', marginTop: '8px' }}>
                    <input
                      type="text"
                      defaultValue={item.notes || ''}
                      onBlur={(e) => handleNotesChange(item.item_id, e.target.value)}
                      placeholder="Add compliance notes or internal audit reference..."
                      className="input input-sm"
                      style={{ width: '100%', fontSize: '0.78rem' }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* TAB 5: REQUIREMENTS EXPLORER (Phase 61) */}
      {activeTab === 'requirements' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.85rem', color: '#64748b' }}>
              Showing {explorerReqs.length} extracted regulatory requirements across indexed instruments.
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {explorerReqs.map((req) => (
              <RequirementCard key={req.requirement_id} requirement={req} />
            ))}
          </div>
        </div>
      )}

      {/* TAB 6: OBLIGATIONS EXPLORER (Phase 62) */}
      {activeTab === 'obligations' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.85rem', color: '#64748b' }}>
              Showing {explorerObs.length} operational regulatory obligations (WHO, WHAT, CONDITIONS, DEADLINES).
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {explorerObs.map((ob) => (
              <ObligationCard key={ob.obligation_id} obligation={ob} />
            ))}
          </div>
        </div>
      )}

      {/* Create Checklist Modal */}
      {showCreateModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
        >
          <div
            style={{
              background: '#ffffff',
              borderRadius: '12px',
              padding: '1.5rem',
              width: '100%',
              maxWidth: '500px',
              boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1)',
            }}
          >
            <h3 style={{ fontSize: '1.15rem', fontWeight: 700, margin: '0 0 1rem 0', color: '#0f172a' }}>
              Generate New Compliance Checklist
            </h3>

            <form onSubmit={handleCreateChecklist}>
              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: '4px' }}>
                  Checklist Title
                </label>
                <input
                  type="text"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  className="input"
                  style={{ width: '100%' }}
                />
              </div>

              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: '4px' }}>
                  Regulatory Authority
                </label>
                <input
                  type="text"
                  value={newAuthority}
                  onChange={(e) => setNewAuthority(e.target.value)}
                  className="input"
                  style={{ width: '100%' }}
                />
              </div>

              <div style={{ marginBottom: '1.5rem' }}>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: '4px' }}>
                  Applicable Entity Profile / Filter
                </label>
                <input
                  type="text"
                  value={newEntityFilter}
                  onChange={(e) => setNewEntityFilter(e.target.value)}
                  placeholder="e.g. Investment Adviser, Broker, AMC..."
                  className="input"
                  style={{ width: '100%' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="btn btn-secondary"
                  disabled={isCreating}
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={isCreating}>
                  {isCreating ? 'Generating Checklist...' : 'Generate Checklist'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Watchlist Modal */}
      <WatchlistModal
        isOpen={showWatchlistModal}
        onClose={() => setShowWatchlistModal(false)}
        onWatchlistSaved={() => {
          loadWatchlistsData();
          setShowWatchlistModal(false);
        }}
        watchlists={watchlists}
      />

      {/* Evidence and Traceability Drawer */}
      <EvidenceDrawer
        checklistId={currentChecklist?.checklist_id || ''}
        item={selectedItemForEvidence}
        onClose={() => setSelectedItemForEvidence(null)}
      />
    </div>
  );
};
