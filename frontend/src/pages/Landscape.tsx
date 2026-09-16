import React, { useState, useEffect } from 'react';
import {
  Layers,
  AlertTriangle,
  Scale,
  RefreshCw,
  Filter,
  ShieldAlert,
} from 'lucide-react';
import {
  RegulatoryOverlap,
  RegulatoryConflict,
} from '../types/api';
import {
  fetchRegulatoryOverlaps,
  fetchRegulatoryConflicts,
  updateRegulatoryConflictStatus,
  triggerOverlapAnalysis,
} from '../api/compliance';

export const Landscape: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'overlaps' | 'conflicts'>('overlaps');
  const [overlaps, setOverlaps] = useState<RegulatoryOverlap[]>([]);
  const [conflicts, setConflicts] = useState<RegulatoryConflict[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedOverlap, setSelectedOverlap] = useState<RegulatoryOverlap | null>(null);
  const [selectedConflict, setSelectedConflict] = useState<RegulatoryConflict | null>(null);
  const [authorityFilter, setAuthorityFilter] = useState('All');
  const [topicFilter, setTopicFilter] = useState('All');
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const authorities = ['All', 'SEBI', 'RBI', 'IRDAI', 'PFRDA', 'IFSCA'];
  const topics = [
    'All',
    'KYC',
    'AML',
    'REPORTING',
    'DISCLOSURE',
    'RISK_MANAGEMENT',
    'GOVERNANCE',
    'RECORD_KEEPING',
    'AUDIT',
    'CYBERSECURITY',
    'CUSTOMER_PROTECTION',
    'CAPITAL',
  ];

  const loadData = async () => {
    setIsLoading(true);
    setStatusMessage(null);
    try {
      const [ovls, cnfs] = await Promise.all([
        fetchRegulatoryOverlaps({
          authority: authorityFilter !== 'All' ? authorityFilter : undefined,
          topic: topicFilter !== 'All' ? topicFilter : undefined,
        }),
        fetchRegulatoryConflicts({
          authority: authorityFilter !== 'All' ? authorityFilter : undefined,
        }),
      ]);
      setOverlaps(ovls);
      setConflicts(cnfs);
      if (ovls.length > 0 && !selectedOverlap) {
        setSelectedOverlap(ovls[0]);
      }
      if (cnfs.length > 0 && !selectedConflict) {
        setSelectedConflict(cnfs[0]);
      }
    } catch (e: any) {
      console.error(e);
      setStatusMessage('Error loading cross-regulator data');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [authorityFilter, topicFilter]);

  const handleTriggerAnalysis = async () => {
    setIsLoading(true);
    setStatusMessage('Scanning requirements for cross-regulator overlaps...');
    try {
      const res = await triggerOverlapAnalysis();
      setStatusMessage(
        `Analysis complete: ${res.overlaps_detected} overlaps, ${res.conflicts_detected} potential inconsistencies identified.`
      );
      await loadData();
    } catch (e: any) {
      setStatusMessage('Failed to run overlap analysis');
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpdateConflict = async (conflictId: string, newStatus: string) => {
    try {
      const updated = await updateRegulatoryConflictStatus(
        conflictId,
        newStatus,
        'compliance_officer',
        `Status updated to ${newStatus} in Landscape dashboard.`
      );
      setConflicts((prev) => prev.map((c) => (c.conflict_id === conflictId ? updated : c)));
      if (selectedConflict?.conflict_id === conflictId) {
        setSelectedConflict(updated);
      }
    } catch (e: any) {
      alert('Failed to update conflict status');
    }
  };

  const highSeverityCount = conflicts.filter((c) => c.severity === 'HIGH').length;
  const mediumSeverityCount = conflicts.filter((c) => c.severity === 'MEDIUM').length;
  const lowSeverityCount = conflicts.filter((c) => c.severity === 'LOW').length;

  return (
    <div style={{ maxWidth: 1400, margin: '0 auto', padding: '2rem 1.5rem' }}>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          marginBottom: '2rem',
          flexWrap: 'wrap',
          gap: '1rem',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.25rem' }}>
            <span style={{ fontSize: '1.75rem' }}>🌐</span>
            <h1 style={{ fontSize: '1.75rem', fontWeight: 700, margin: 0, color: '#f8fafc' }}>
              Regulatory Landscape & Conflict Intelligence
            </h1>
          </div>
          <p style={{ color: '#94a3b8', margin: 0, fontSize: '0.95rem' }}>
            Cross-regulator overlap detection and conservative potential inconsistency analysis across SEBI, RBI, IRDAI, PFRDA, and IFSCA.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button
            onClick={handleTriggerAnalysis}
            disabled={isLoading}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              backgroundColor: '#3b82f6',
              color: 'white',
              border: 'none',
              padding: '0.6rem 1.2rem',
              borderRadius: '0.5rem',
              fontWeight: 600,
              cursor: isLoading ? 'not-allowed' : 'pointer',
            }}
          >
            <RefreshCw size={16} className={isLoading ? 'animate-spin' : ''} />
            Scan Overlaps
          </button>
        </div>
      </div>

      {statusMessage && (
        <div
          style={{
            padding: '0.75rem 1rem',
            backgroundColor: '#1e293b',
            border: '1px solid #334155',
            borderRadius: '0.5rem',
            color: '#38bdf8',
            marginBottom: '1.5rem',
            fontSize: '0.9rem',
          }}
        >
          {statusMessage}
        </div>
      )}

      {/* Filter & Metric Bar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          backgroundColor: '#0f172a',
          border: '1px solid #1e293b',
          borderRadius: '0.75rem',
          padding: '1rem 1.25rem',
          marginBottom: '1.5rem',
          flexWrap: 'wrap',
          gap: '1rem',
        }}
      >
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Filter size={16} color="#94a3b8" />
            <span style={{ fontSize: '0.85rem', color: '#94a3b8', fontWeight: 600 }}>Authority:</span>
            <select
              value={authorityFilter}
              onChange={(e) => setAuthorityFilter(e.target.value)}
              style={{
                backgroundColor: '#1e293b',
                color: '#f8fafc',
                border: '1px solid #334155',
                padding: '0.4rem 0.75rem',
                borderRadius: '0.375rem',
                fontSize: '0.85rem',
              }}
            >
              {authorities.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.85rem', color: '#94a3b8', fontWeight: 600 }}>Topic:</span>
            <select
              value={topicFilter}
              onChange={(e) => setTopicFilter(e.target.value)}
              style={{
                backgroundColor: '#1e293b',
                color: '#f8fafc',
                border: '1px solid #334155',
                padding: '0.4rem 0.75rem',
                borderRadius: '0.375rem',
                fontSize: '0.85rem',
              }}
            >
              {topics.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Conflict Severity Summary */}
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          <span style={{ fontSize: '0.85rem', color: '#94a3b8' }}>Potential Inconsistencies:</span>
          <span
            style={{
              padding: '0.2rem 0.5rem',
              borderRadius: '0.25rem',
              backgroundColor: 'rgba(239, 68, 68, 0.2)',
              color: '#f87171',
              fontSize: '0.8rem',
              fontWeight: 700,
            }}
          >
            {highSeverityCount} HIGH
          </span>
          <span
            style={{
              padding: '0.2rem 0.5rem',
              borderRadius: '0.25rem',
              backgroundColor: 'rgba(245, 158, 11, 0.2)',
              color: '#fbbf24',
              fontSize: '0.8rem',
              fontWeight: 700,
            }}
          >
            {mediumSeverityCount} MEDIUM
          </span>
          <span
            style={{
              padding: '0.2rem 0.5rem',
              borderRadius: '0.25rem',
              backgroundColor: 'rgba(59, 130, 246, 0.2)',
              color: '#60a5fa',
              fontSize: '0.8rem',
              fontWeight: 700,
            }}
          >
            {lowSeverityCount} LOW
          </span>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid #334155', marginBottom: '1.5rem', gap: '1rem' }}>
        <button
          onClick={() => setActiveTab('overlaps')}
          style={{
            padding: '0.75rem 1.5rem',
            backgroundColor: 'transparent',
            border: 'none',
            borderBottom: activeTab === 'overlaps' ? '2px solid #3b82f6' : '2px solid transparent',
            color: activeTab === 'overlaps' ? '#3b82f6' : '#94a3b8',
            fontWeight: 600,
            fontSize: '1rem',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
          }}
        >
          <Layers size={18} />
          Regulatory Overlaps ({overlaps.length})
        </button>

        <button
          onClick={() => setActiveTab('conflicts')}
          style={{
            padding: '0.75rem 1.5rem',
            backgroundColor: 'transparent',
            border: 'none',
            borderBottom: activeTab === 'conflicts' ? '2px solid #ef4444' : '2px solid transparent',
            color: activeTab === 'conflicts' ? '#ef4444' : '#94a3b8',
            fontWeight: 600,
            fontSize: '1rem',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
          }}
        >
          <AlertTriangle size={18} />
          Potential Inconsistencies ({conflicts.length})
        </button>
      </div>

      {/* Tab 1: Regulatory Overlaps */}
      {activeTab === 'overlaps' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.2fr', gap: '1.5rem' }}>
          {/* Overlaps List */}
          <div
            style={{
              backgroundColor: '#0f172a',
              borderRadius: '0.75rem',
              border: '1px solid #1e293b',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                padding: '0.75rem 1rem',
                borderBottom: '1px solid #1e293b',
                fontWeight: 600,
                color: '#cbd5e1',
                fontSize: '0.9rem',
              }}
            >
              Detected Cross-Regulator Relationships
            </div>

            {overlaps.length === 0 ? (
              <div style={{ padding: '2rem', textAlign: 'center', color: '#64748b' }}>
                No regulatory overlaps found matching selected filters. Click "Scan Overlaps" to analyze.
              </div>
            ) : (
              <div style={{ maxHeight: 600, overflowY: 'auto' }}>
                {overlaps.map((ovl) => {
                  const isSelected = selectedOverlap?.overlap_id === ovl.overlap_id;
                  return (
                    <div
                      key={ovl.overlap_id}
                      onClick={() => setSelectedOverlap(ovl)}
                      style={{
                        padding: '1rem',
                        borderBottom: '1px solid #1e293b',
                        backgroundColor: isSelected ? '#1e293b' : 'transparent',
                        cursor: 'pointer',
                        transition: 'background 0.15s',
                      }}
                    >
                      <div
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          marginBottom: '0.5rem',
                        }}
                      >
                        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                          <span
                            style={{
                              padding: '0.2rem 0.5rem',
                              borderRadius: '0.25rem',
                              backgroundColor: '#334155',
                              color: '#38bdf8',
                              fontSize: '0.75rem',
                              fontWeight: 700,
                            }}
                          >
                            {ovl.left_authority}
                          </span>
                          <span style={{ color: '#64748b', fontSize: '0.8rem' }}>↔</span>
                          <span
                            style={{
                              padding: '0.2rem 0.5rem',
                              borderRadius: '0.25rem',
                              backgroundColor: '#334155',
                              color: '#38bdf8',
                              fontSize: '0.75rem',
                              fontWeight: 700,
                            }}
                          >
                            {ovl.right_authority}
                          </span>
                        </div>

                        <span
                          style={{
                            padding: '0.2rem 0.6rem',
                            borderRadius: '1rem',
                            fontSize: '0.75rem',
                            fontWeight: 600,
                            backgroundColor:
                              ovl.relationship_type === 'IDENTICAL' || ovl.relationship_type === 'NEAR_DUPLICATE'
                                ? 'rgba(34, 197, 94, 0.2)'
                                : ovl.relationship_type === 'OVERLAPPING'
                                ? 'rgba(59, 130, 246, 0.2)'
                                : 'rgba(148, 163, 184, 0.2)',
                            color:
                              ovl.relationship_type === 'IDENTICAL' || ovl.relationship_type === 'NEAR_DUPLICATE'
                                ? '#4ade80'
                                : ovl.relationship_type === 'OVERLAPPING'
                                ? '#60a5fa'
                                : '#cbd5e1',
                          }}
                        >
                          {ovl.relationship_type}
                        </span>
                      </div>

                      <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#f1f5f9', marginBottom: '0.25rem' }}>
                        Topic: {ovl.shared_topic || 'General'}
                      </div>
                      <div style={{ fontSize: '0.8rem', color: '#94a3b8', lineHeight: 1.4 }}>
                        {ovl.reasoning ? ovl.reasoning.substring(0, 110) + '...' : 'No explanation recorded.'}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Side-by-Side Overlap Detail (73.18) */}
          <div
            style={{
              backgroundColor: '#0f172a',
              borderRadius: '0.75rem',
              border: '1px solid #1e293b',
              padding: '1.5rem',
            }}
          >
            {selectedOverlap ? (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                  <h3 style={{ margin: 0, fontSize: '1.2rem', color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <Scale size={20} color="#38bdf8" />
                    Side-by-Side Comparison
                  </h3>
                  <span style={{ fontSize: '0.8rem', color: '#64748b' }}>
                    Confidence: <strong style={{ color: '#cbd5e1' }}>{selectedOverlap.confidence}</strong>
                  </span>
                </div>

                <div
                  style={{
                    padding: '0.75rem',
                    backgroundColor: '#1e293b',
                    borderRadius: '0.5rem',
                    marginBottom: '1.25rem',
                    fontSize: '0.85rem',
                    color: '#94a3b8',
                  }}
                >
                  <strong style={{ color: '#f8fafc' }}>Why Classified as {selectedOverlap.relationship_type}: </strong>
                  {selectedOverlap.reasoning}
                </div>

                {/* Left vs Right Comparison Grid */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>
                  {/* Left Provision */}
                  <div
                    style={{
                      border: '1px solid #334155',
                      borderRadius: '0.5rem',
                      padding: '1rem',
                      backgroundColor: 'rgba(15, 23, 42, 0.6)',
                    }}
                  >
                    <div style={{ fontWeight: 700, color: '#38bdf8', marginBottom: '0.5rem', fontSize: '0.9rem' }}>
                      {selectedOverlap.left_authority}
                    </div>
                    <div style={{ fontSize: '0.78rem', color: '#94a3b8', marginBottom: '0.5rem' }}>
                      Doc: {selectedOverlap.left_document_id}
                    </div>
                    <div style={{ fontSize: '0.82rem', color: '#e2e8f0', lineHeight: 1.5, marginBottom: '0.75rem' }}>
                      <strong>Evidence:</strong>
                      <div
                        style={{
                          backgroundColor: '#020617',
                          padding: '0.6rem',
                          borderRadius: '0.375rem',
                          marginTop: '0.25rem',
                          fontFamily: 'monospace',
                          fontSize: '0.75rem',
                          maxHeight: 140,
                          overflowY: 'auto',
                        }}
                      >
                        {selectedOverlap.evidence_left}
                      </div>
                    </div>
                  </div>

                  {/* Right Provision */}
                  <div
                    style={{
                      border: '1px solid #334155',
                      borderRadius: '0.5rem',
                      padding: '1rem',
                      backgroundColor: 'rgba(15, 23, 42, 0.6)',
                    }}
                  >
                    <div style={{ fontWeight: 700, color: '#38bdf8', marginBottom: '0.5rem', fontSize: '0.9rem' }}>
                      {selectedOverlap.right_authority}
                    </div>
                    <div style={{ fontSize: '0.78rem', color: '#94a3b8', marginBottom: '0.5rem' }}>
                      Doc: {selectedOverlap.right_document_id}
                    </div>
                    <div style={{ fontSize: '0.82rem', color: '#e2e8f0', lineHeight: 1.5, marginBottom: '0.75rem' }}>
                      <strong>Evidence:</strong>
                      <div
                        style={{
                          backgroundColor: '#020617',
                          padding: '0.6rem',
                          borderRadius: '0.375rem',
                          marginTop: '0.25rem',
                          fontFamily: 'monospace',
                          fontSize: '0.75rem',
                          maxHeight: 140,
                          overflowY: 'auto',
                        }}
                      >
                        {selectedOverlap.evidence_right}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Structured Dimensions Table */}
                <div style={{ border: '1px solid #1e293b', borderRadius: '0.5rem', overflow: 'hidden' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
                    <tbody>
                      <tr style={{ borderBottom: '1px solid #1e293b' }}>
                        <td style={{ padding: '0.6rem 0.75rem', color: '#94a3b8', fontWeight: 600 }}>Shared Topic</td>
                        <td style={{ padding: '0.6rem 0.75rem', color: '#f8fafc' }}>
                          {selectedOverlap.shared_topic || 'N/A'}
                        </td>
                      </tr>
                      <tr style={{ borderBottom: '1px solid #1e293b' }}>
                        <td style={{ padding: '0.6rem 0.75rem', color: '#94a3b8', fontWeight: 600 }}>Shared Activity</td>
                        <td style={{ padding: '0.6rem 0.75rem', color: '#f8fafc' }}>
                          {selectedOverlap.shared_activity || 'N/A'}
                        </td>
                      </tr>
                      <tr style={{ borderBottom: '1px solid #1e293b' }}>
                        <td style={{ padding: '0.6rem 0.75rem', color: '#94a3b8', fontWeight: 600 }}>Entity Applicability</td>
                        <td style={{ padding: '0.6rem 0.75rem', color: '#f8fafc' }}>
                          {selectedOverlap.applicability_match || 'UNKNOWN'}
                        </td>
                      </tr>
                      <tr>
                        <td style={{ padding: '0.6rem 0.75rem', color: '#94a3b8', fontWeight: 600 }}>Similarity Signal</td>
                        <td style={{ padding: '0.6rem 0.75rem', color: '#f8fafc' }}>
                          {(selectedOverlap.similarity_score * 100).toFixed(1)}%
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <div style={{ padding: '3rem', textAlign: 'center', color: '#64748b' }}>
                Select an overlap record to inspect side-by-side evidence and attributes.
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 2: Potential Inconsistencies & Conflicts (Phase 74) */}
      {activeTab === 'conflicts' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.2fr', gap: '1.5rem' }}>
          {/* Conflicts List */}
          <div
            style={{
              backgroundColor: '#0f172a',
              borderRadius: '0.75rem',
              border: '1px solid #1e293b',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                padding: '0.75rem 1rem',
                borderBottom: '1px solid #1e293b',
                fontWeight: 600,
                color: '#cbd5e1',
                fontSize: '0.9rem',
              }}
            >
              Potential Inconsistencies Requiring Compliance Review
            </div>

            {conflicts.length === 0 ? (
              <div style={{ padding: '2rem', textAlign: 'center', color: '#64748b' }}>
                No potential regulatory inconsistencies detected. Requirements are currently harmonious.
              </div>
            ) : (
              <div style={{ maxHeight: 600, overflowY: 'auto' }}>
                {conflicts.map((cnf) => {
                  const isSelected = selectedConflict?.conflict_id === cnf.conflict_id;
                  return (
                    <div
                      key={cnf.conflict_id}
                      onClick={() => setSelectedConflict(cnf)}
                      style={{
                        padding: '1rem',
                        borderBottom: '1px solid #1e293b',
                        backgroundColor: isSelected ? '#1e293b' : 'transparent',
                        cursor: 'pointer',
                        transition: 'background 0.15s',
                      }}
                    >
                      <div
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          marginBottom: '0.5rem',
                        }}
                      >
                        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                          <span
                            style={{
                              padding: '0.2rem 0.5rem',
                              borderRadius: '0.25rem',
                              backgroundColor: '#334155',
                              color: '#38bdf8',
                              fontSize: '0.75rem',
                              fontWeight: 700,
                            }}
                          >
                            {cnf.left_authority}
                          </span>
                          <span style={{ color: '#64748b', fontSize: '0.8rem' }}>vs</span>
                          <span
                            style={{
                              padding: '0.2rem 0.5rem',
                              borderRadius: '0.25rem',
                              backgroundColor: '#334155',
                              color: '#38bdf8',
                              fontSize: '0.75rem',
                              fontWeight: 700,
                            }}
                          >
                            {cnf.right_authority}
                          </span>
                        </div>

                        <span
                          style={{
                            padding: '0.2rem 0.5rem',
                            borderRadius: '0.25rem',
                            fontSize: '0.75rem',
                            fontWeight: 700,
                            backgroundColor:
                              cnf.severity === 'HIGH'
                                ? 'rgba(239, 68, 68, 0.2)'
                                : cnf.severity === 'MEDIUM'
                                ? 'rgba(245, 158, 11, 0.2)'
                                : 'rgba(59, 130, 246, 0.2)',
                            color:
                              cnf.severity === 'HIGH'
                                ? '#f87171'
                                : cnf.severity === 'MEDIUM'
                                ? '#fbbf24'
                                : '#60a5fa',
                          }}
                        >
                          {cnf.severity}
                        </span>
                      </div>

                      <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#f87171', marginBottom: '0.25rem' }}>
                        {cnf.conflict_type}
                      </div>
                      <div style={{ fontSize: '0.8rem', color: '#94a3b8', lineHeight: 1.4 }}>
                        {cnf.explanation ? cnf.explanation.substring(0, 110) + '...' : 'Review required.'}
                      </div>

                      <div style={{ marginTop: '0.5rem', display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem' }}>
                        <span style={{ color: '#64748b' }}>Status: {cnf.resolution_status}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Conflict Detail & Review Actions (74.17, 74.21) */}
          <div
            style={{
              backgroundColor: '#0f172a',
              borderRadius: '0.75rem',
              border: '1px solid #1e293b',
              padding: '1.5rem',
            }}
          >
            {selectedConflict ? (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                  <h3 style={{ margin: 0, fontSize: '1.2rem', color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <ShieldAlert size={20} color="#f87171" />
                    Potential Regulatory Inconsistency Detail
                  </h3>
                  <span
                    style={{
                      padding: '0.25rem 0.75rem',
                      borderRadius: '1rem',
                      fontSize: '0.8rem',
                      fontWeight: 700,
                      backgroundColor:
                        selectedConflict.resolution_status === 'RESOLVED'
                          ? 'rgba(34, 197, 94, 0.2)'
                          : selectedConflict.resolution_status === 'UNDER_REVIEW'
                          ? 'rgba(245, 158, 11, 0.2)'
                          : 'rgba(239, 68, 68, 0.2)',
                      color:
                        selectedConflict.resolution_status === 'RESOLVED'
                          ? '#4ade80'
                          : selectedConflict.resolution_status === 'UNDER_REVIEW'
                          ? '#fbbf24'
                          : '#f87171',
                    }}
                  >
                    {selectedConflict.resolution_status}
                  </span>
                </div>

                <div
                  style={{
                    padding: '0.75rem',
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    border: '1px solid rgba(239, 68, 68, 0.2)',
                    borderRadius: '0.5rem',
                    marginBottom: '1.25rem',
                    fontSize: '0.85rem',
                    color: '#fca5a5',
                  }}
                >
                  <strong>Why Flagged: </strong>
                  {selectedConflict.explanation}
                </div>

                {/* Evidence Comparison */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>
                  <div style={{ border: '1px solid #334155', borderRadius: '0.5rem', padding: '1rem' }}>
                    <div style={{ fontWeight: 700, color: '#38bdf8', marginBottom: '0.25rem' }}>
                      {selectedConflict.left_authority} Mandate
                    </div>
                    <div
                      style={{
                        backgroundColor: '#020617',
                        padding: '0.6rem',
                        borderRadius: '0.375rem',
                        fontSize: '0.75rem',
                        fontFamily: 'monospace',
                        color: '#cbd5e1',
                        maxHeight: 120,
                        overflowY: 'auto',
                      }}
                    >
                      {selectedConflict.evidence_left}
                    </div>
                  </div>

                  <div style={{ border: '1px solid #334155', borderRadius: '0.5rem', padding: '1rem' }}>
                    <div style={{ fontWeight: 700, color: '#38bdf8', marginBottom: '0.25rem' }}>
                      {selectedConflict.right_authority} Mandate
                    </div>
                    <div
                      style={{
                        backgroundColor: '#020617',
                        padding: '0.6rem',
                        borderRadius: '0.375rem',
                        fontSize: '0.75rem',
                        fontFamily: 'monospace',
                        color: '#cbd5e1',
                        maxHeight: 120,
                        overflowY: 'auto',
                      }}
                    >
                      {selectedConflict.evidence_right}
                    </div>
                  </div>
                </div>

                {/* Human Review Actions (74.17) */}
                <div style={{ borderTop: '1px solid #334155', paddingTop: '1rem' }}>
                  <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#94a3b8', marginBottom: '0.75rem' }}>
                    Compliance Officer Review Actions:
                  </div>
                  <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                    <button
                      onClick={() => handleUpdateConflict(selectedConflict.conflict_id, 'UNDER_REVIEW')}
                      style={{
                        backgroundColor: '#f59e0b',
                        color: 'white',
                        border: 'none',
                        padding: '0.4rem 0.8rem',
                        borderRadius: '0.375rem',
                        fontSize: '0.8rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                      }}
                    >
                      Mark Under Review
                    </button>
                    <button
                      onClick={() => handleUpdateConflict(selectedConflict.conflict_id, 'RESOLVED')}
                      style={{
                        backgroundColor: '#10b981',
                        color: 'white',
                        border: 'none',
                        padding: '0.4rem 0.8rem',
                        borderRadius: '0.375rem',
                        fontSize: '0.8rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                      }}
                    >
                      Mark Resolved
                    </button>
                    <button
                      onClick={() => handleUpdateConflict(selectedConflict.conflict_id, 'DISMISSED')}
                      style={{
                        backgroundColor: '#64748b',
                        color: 'white',
                        border: 'none',
                        padding: '0.4rem 0.8rem',
                        borderRadius: '0.375rem',
                        fontSize: '0.8rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                      }}
                    >
                      Dismiss (Harmonious)
                    </button>
                    <button
                      onClick={() => handleUpdateConflict(selectedConflict.conflict_id, 'FALSE_POSITIVE')}
                      style={{
                        backgroundColor: '#334155',
                        color: '#94a3b8',
                        border: 'none',
                        padding: '0.4rem 0.8rem',
                        borderRadius: '0.375rem',
                        fontSize: '0.8rem',
                        cursor: 'pointer',
                      }}
                    >
                      False Positive
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div style={{ padding: '3rem', textAlign: 'center', color: '#64748b' }}>
                Select a potential inconsistency to inspect conflicting parameters and evidence.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
