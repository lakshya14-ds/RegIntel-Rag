import React, { useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import {
  MessageSquareText,
  Scale,
  FileText,
  Search,
  Info,
  Home,
  Menu,
  X,
  RefreshCw,
} from 'lucide-react';
import { StatusPill } from '../common/StatusPill';
import { useHealth } from '../../hooks/useHealth';

export const AppLayout: React.FC = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { health, isLoading: isHealthLoading, refetch: refetchHealth } = useHealth(true);
  const location = useLocation();

  const navItems = [
    { to: '/', label: 'Overview', icon: Home },
    { to: '/ask', label: 'Ask RegIntel', icon: MessageSquareText },
    { to: '/compare', label: 'Compare Regulations', icon: Scale },
    { to: '/latest', label: 'Latest Regulations', icon: FileText },
    { to: '/search', label: 'Search Documents', icon: Search },
    { to: '/about', label: 'About & Metrics', icon: Info },
  ];

  return (
    <div className="app-container">
      {/* Mobile Backdrop */}
      {sidebarOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0,0,0,0.5)',
            zIndex: 35,
          }}
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
          <div style={{ fontSize: '1.5rem' }}>⚖️</div>
          <div>
            <div className="sidebar-brand">RegIntel RAG</div>
            <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>
              Regulatory Intelligence
            </div>
          </div>
          <button
            onClick={() => setSidebarOpen(false)}
            style={{
              marginLeft: 'auto',
              background: 'none',
              border: 'none',
              color: '#94a3b8',
              cursor: 'pointer',
              display: 'none',
            }}
            aria-label="Close Sidebar"
          >
            <X size={20} />
          </button>
        </div>

        <nav className="sidebar-nav">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.to;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={`nav-link ${isActive ? 'active' : ''}`}
                onClick={() => setSidebarOpen(false)}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        <div className="sidebar-footer">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontWeight: 600, color: '#e2e8f0' }}>Backend Status</span>
            <button
              onClick={() => refetchHealth()}
              style={{
                background: 'none',
                border: 'none',
                color: '#94a3b8',
                cursor: 'pointer',
                padding: '2px',
              }}
              title="Refresh API Status"
            >
              <RefreshCw size={13} className={isHealthLoading ? 'animate-spin' : ''} />
            </button>
          </div>
          <StatusPill health={health} isLoading={isHealthLoading} />
          <div style={{ marginTop: '10px', fontSize: '0.72rem', color: '#64748b' }}>
            SEBI Corpus • v1.0.0
          </div>
        </div>
      </aside>

      {/* Main Area */}
      <div className="main-content">
        <header className="top-header">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            style={{
              background: 'none',
              border: 'none',
              color: '#475569',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              padding: '6px',
            }}
            aria-label="Toggle Navigation"
          >
            <Menu size={22} />
          </button>

          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <StatusPill health={health} isLoading={isHealthLoading} />
          </div>
        </header>

        <main style={{ flex: 1 }}>
          <Outlet />
        </main>
      </div>
    </div>
  );
};
