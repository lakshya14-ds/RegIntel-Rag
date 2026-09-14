import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ClipboardCheck,
  PlusCircle,
  AlertTriangle,
  FileText,
  RefreshCw,
  Scale,
} from 'lucide-react';
import {
  ComplianceChecklist,
  ChecklistItem,
  ChecklistStatus,
  RegulatoryRequirement,
  RegulatoryObligation,
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
} from '../api/compliance';
import { ChecklistProgressDashboard } from '../components/compliance/ChecklistProgressDashboard';
import { EvidenceDrawer } from '../components/compliance/EvidenceDrawer';
import { RequirementCard } from '../components/compliance/RequirementCard';
import { ObligationCard } from '../components/compliance/ObligationCard';

export const Compliance: React.FC = () => {
  const { checklistId } = useParams<{ checklistId?: string }>();
  const navigate = useNavigate();

  // Tab State: 'checklists' | 'requirements' | 'obligations'
  const [activeTab, setActiveTab] = useState<'checklists' | 'requirements' | 'obligations'>('checklists');

  // Checklists State
  const [checklists, setChecklists] = useState<ComplianceChecklist[]>([]);
  const [currentChecklist, setCurrentChecklist] = useState<ComplianceChecklist | null>(null);
  const [selectedItemForEvidence, setSelectedItemForEvidence] = useState<ChecklistItem | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [isLoading, setIsLoading] = useState(false);
  const [isRegenerating, setIsRegenerating] = useState(false);

  // New Checklist Modal State
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newTitle, setNewTitle] = useState('SEBI Comprehensive Compliance Checklist');
  const [newAuthority, setNewAuthority] = useState('SEBI');
  const [newEntityFilter, setNewEntityFilter] = useState('Investment Adviser');
  const [isCreating, setIsCreating] = useState(false);

  // Requirements & Obligations Explorer State
  const [explorerReqs, setExplorerReqs] = useState<RegulatoryRequirement[]>([]);
  const [explorerObs, setExplorerObs] = useState<RegulatoryObligation[]>([]);

  // Load Checklists List
  useEffect(() => {
    fetchChecklists()
      .then((data) => {
        setChecklists(data);
        if (checklistId) {
          const target = data.find((c) => c.checklist_id === checklistId);
          if (target) setCurrentChecklist(target);
          else loadChecklistDetail(checklistId);
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

  return (
    <div className="page-container">
      {/* Top Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 800, color: '#0f172a', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ClipboardCheck size={28} style={{ color: '#2563eb' }} />
            Compliance & Regulatory Intelligence
          </h1>
          <p style={{ color: '#64748b', fontSize: '0.88rem', margin: '4px 0 0 0' }}>
            Convert SEBI regulations into structured requirements, operational obligations, and audited checklists.
          </p>
        </div>

        <button
          onClick={() => setShowCreateModal(true)}
          className="btn btn-primary"
          style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
        >
          <PlusCircle size={16} /> Generate New Checklist
        </button>
      </div>

      {/* Navigation Tabs */}
      <div style={{ display: 'flex', gap: '0.5rem', borderBottom: '2px solid #e2e8f0', marginBottom: '1.5rem' }}>
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
          }}
        >
          Operational Obligations (Phase 62)
        </button>
      </div>

      {/* TAB 1: COMPLIANCE CHECKLISTS */}
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
                style={{ maxWidth: '280px', fontSize: '0.82rem' }}
              >
                {checklists.map((chk) => (
                  <option key={chk.checklist_id} value={chk.checklist_id}>
                    {chk.title} ({chk.completion_rate}%)
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* Checklist Items List */}
          {isLoading ? (
            <div className="card" style={{ textAlign: 'center', padding: '3rem 1rem', color: '#64748b' }}>
              <RefreshCw size={24} className="animate-spin" style={{ margin: '0 auto 0.5rem auto', color: '#2563eb' }} />
              Loading checklist details...
            </div>
          ) : filteredItems.length === 0 ? (
            <div className="card" style={{ textAlign: 'center', padding: '3rem 1rem', color: '#64748b' }}>
              <p>No checklist items match the current status filter.</p>
            </div>
          ) : (
            filteredItems.map((item, idx) => (
              <div
                key={item.item_id}
                className="card"
                style={{
                  padding: '1.25rem',
                  marginBottom: '0.75rem',
                  borderLeft: `4px solid ${
                    item.status === 'COMPLIANT'
                      ? '#10b981'
                      : item.status === 'NON_COMPLIANT'
                      ? '#ef4444'
                      : item.status === 'NEEDS_REVIEW'
                      ? '#f59e0b'
                      : '#cbd5e1'
                  }`,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.5rem' }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                      <span style={{ fontWeight: 800, color: '#3b82f6', fontSize: '0.9rem' }}>#{idx + 1}</span>
                      <h4 style={{ margin: 0, fontSize: '1rem', fontWeight: 700, color: '#1e293b' }}>
                        {item.control_question}
                      </h4>
                    </div>

                    {item.is_changed && (
                      <div
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          marginTop: '4px',
                          padding: '2px 8px',
                          backgroundColor: '#fef3c7',
                          color: '#b45309',
                          borderRadius: '12px',
                          fontSize: '0.74rem',
                          fontWeight: 700,
                        }}
                      >
                        <AlertTriangle size={12} />
                        Recent Regulatory Change: {item.change_summary}
                      </div>
                    )}
                  </div>

                  {/* Status Dropdown */}
                  <select
                    value={item.status}
                    onChange={(e) => handleStatusChange(item.item_id, e.target.value as ChecklistStatus)}
                    style={{
                      padding: '4px 8px',
                      borderRadius: 'var(--radius-sm)',
                      fontWeight: 700,
                      fontSize: '0.82rem',
                      border: '1px solid #cbd5e1',
                      backgroundColor:
                        item.status === 'COMPLIANT'
                          ? '#ecfdf5'
                          : item.status === 'NON_COMPLIANT'
                          ? '#fef2f2'
                          : item.status === 'NEEDS_REVIEW'
                          ? '#fffbeb'
                          : '#ffffff',
                    }}
                  >
                    <option value="NOT_REVIEWED">⏳ Not Reviewed</option>
                    <option value="COMPLIANT">✅ Compliant</option>
                    <option value="NON_COMPLIANT">❌ Non-Compliant</option>
                    <option value="PARTIALLY_COMPLIANT">⚠️ Partially Compliant</option>
                    <option value="NEEDS_REVIEW">🔍 Needs Review</option>
                    <option value="NOT_APPLICABLE">⚪ Not Applicable</option>
                  </select>
                </div>

                <div style={{ fontSize: '0.86rem', color: '#475569', marginBottom: '0.5rem' }}>
                  <strong>Required Action:</strong> {item.compliance_action}
                </div>

                {/* Proof & Traceability Buttons */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.75rem', paddingTop: '0.5rem', borderTop: '1px solid #f1f5f9' }}>
                  <div style={{ fontSize: '0.78rem', color: '#64748b' }}>
                    {item.evidence_required && item.evidence_required.length > 0 && (
                      <span>
                        <strong>Required Evidence:</strong> {item.evidence_required.join(', ')}
                      </span>
                    )}
                  </div>

                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button
                      onClick={() => setSelectedItemForEvidence(item)}
                      className="btn btn-secondary btn-sm"
                      style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '0.76rem' }}
                    >
                      <FileText size={13} /> View Audit Trail & Evidence
                    </button>
                    {item.is_changed && (
                      <button
                        onClick={() => navigate(`/compare?docA=${item.document_id}`)}
                        className="btn btn-outline btn-sm"
                        style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '0.76rem' }}
                      >
                        <Scale size={13} /> View What Changed
                      </button>
                    )}
                  </div>
                </div>

                {/* Review Notes Area */}
                <div style={{ marginTop: '0.5rem' }}>
                  <input
                    type="text"
                    defaultValue={item.notes || ''}
                    placeholder="Add internal audit notes or verification reference..."
                    onBlur={(e) => handleNotesChange(item.item_id, e.target.value)}
                    style={{
                      width: '100%',
                      padding: '4px 8px',
                      fontSize: '0.8rem',
                      borderRadius: 'var(--radius-sm)',
                      border: '1px solid #e2e8f0',
                      backgroundColor: '#f8fafc',
                    }}
                  />
                </div>
              </div>
            ))
          )}
        </>
      )}

      {/* TAB 2: EXTRACTED REQUIREMENTS EXPLORER */}
      {activeTab === 'requirements' && (
        <div>
          <p style={{ color: '#64748b', fontSize: '0.88rem', marginBottom: '1rem' }}>
            Browse structured regulatory requirements extracted across ingested SEBI circulars and regulations.
          </p>
          {explorerReqs.length === 0 ? (
            <div className="card" style={{ padding: '2rem', textAlign: 'center' }}>
              <RefreshCw size={24} className="animate-spin" style={{ margin: '0 auto 0.5rem auto', color: '#2563eb' }} />
              Loading extracted requirements...
            </div>
          ) : (
            explorerReqs.map((req) => <RequirementCard key={req.requirement_id} requirement={req} />)
          )}
        </div>
      )}

      {/* TAB 3: OPERATIONAL OBLIGATIONS EXPLORER */}
      {activeTab === 'obligations' && (
        <div>
          <p style={{ color: '#64748b', fontSize: '0.88rem', marginBottom: '1rem' }}>
            Inspect operational regulatory obligations categorized by deontic force (WHO, WHAT, WHEN, CONDITIONS, EVIDENCE).
          </p>
          {explorerObs.length === 0 ? (
            <div className="card" style={{ padding: '2rem', textAlign: 'center' }}>
              <RefreshCw size={24} className="animate-spin" style={{ margin: '0 auto 0.5rem auto', color: '#2563eb' }} />
              Loading operational obligations...
            </div>
          ) : (
            explorerObs.map((ob) => <ObligationCard key={ob.obligation_id} obligation={ob} />)
          )}
        </div>
      )}

      {/* Generate Checklist Modal */}
      {showCreateModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            zIndex: 50,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '1rem',
          }}
        >
          <div className="card" style={{ width: '100%', maxWidth: '500px', padding: '1.75rem', backgroundColor: '#ffffff' }}>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 800, margin: '0 0 1rem 0', color: '#0f172a' }}>
              Generate Regulatory Compliance Checklist
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
                  required
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

      {/* Evidence and Traceability Drawer */}
      <EvidenceDrawer
        checklistId={currentChecklist?.checklist_id || ''}
        item={selectedItemForEvidence}
        onClose={() => setSelectedItemForEvidence(null)}
      />
    </div>
  );
};
