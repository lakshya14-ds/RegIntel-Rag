import React, { useState } from 'react';
import { X, Eye, Plus } from 'lucide-react';
import { Watchlist } from '../../types/api';
import { saveWatchlist } from '../../api/compliance';

interface WatchlistModalProps {
  isOpen: boolean;
  onClose: () => void;
  onWatchlistSaved: () => void;
  watchlists: Watchlist[];
}

export const WatchlistModal: React.FC<WatchlistModalProps> = ({
  isOpen,
  onClose,
  onWatchlistSaved,
  watchlists,
}) => {
  const [name, setName] = useState('');
  const [authority, setAuthority] = useState('SEBI');
  const [documentId, setDocumentId] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  if (!isOpen) return null;

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    setIsSaving(true);
    try {
      await saveWatchlist({
        name: name.trim(),
        authorities: authority ? [authority] : ['SEBI'],
        document_ids: documentId.trim() ? [documentId.trim()] : [],
        is_active: true,
      });
      setName('');
      setDocumentId('');
      onWatchlistSaved();
    } catch (err) {
      console.error('Failed to create watchlist:', err);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md p-6 shadow-2xl space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Eye className="w-5 h-5 text-sky-400" />
            <h3 className="text-lg font-semibold text-slate-100">Regulatory Watchlists</h3>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-200">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Existing watchlists */}
        <div>
          <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
            Active Watchlists ({watchlists.length})
          </h4>
          {watchlists.length === 0 ? (
            <p className="text-xs text-slate-500 italic">No custom watchlists created yet.</p>
          ) : (
            <div className="space-y-2 max-h-36 overflow-y-auto pr-1">
              {watchlists.map((w) => (
                <div
                  key={w.watchlist_id}
                  className="bg-slate-800/80 border border-slate-700/60 p-2.5 rounded-lg flex items-center justify-between text-xs"
                >
                  <div>
                    <span className="font-medium text-slate-200 block">{w.name}</span>
                    <span className="text-slate-400 text-[11px]">
                      {w.authorities.join(', ') || 'All Authorities'} •{' '}
                      {w.document_ids.length > 0 ? `${w.document_ids.length} doc(s)` : 'All Documents'}
                    </span>
                  </div>
                  <span className="text-emerald-400 bg-emerald-950/40 border border-emerald-800/40 px-2 py-0.5 rounded text-[10px] font-semibold">
                    ACTIVE
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Create new */}
        <form onSubmit={handleCreate} className="space-y-3 pt-3 border-t border-slate-800">
          <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
            Create New Watchlist
          </h4>

          <div>
            <label className="text-xs text-slate-400 block mb-1">Watchlist Name</label>
            <input
              type="text"
              placeholder="e.g. Mutual Funds & ESG Regulations"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-sky-500"
              required
            />
          </div>

          <div>
            <label className="text-xs text-slate-400 block mb-1">Authority</label>
            <select
              value={authority}
              onChange={(e) => setAuthority(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-sky-500"
            >
              <option value="SEBI">SEBI</option>
              <option value="RBI">RBI</option>
              <option value="IFSCA">IFSCA</option>
            </select>
          </div>

          <div>
            <label className="text-xs text-slate-400 block mb-1">Specific Document ID (Optional)</label>
            <input
              type="text"
              placeholder="e.g. sebi_cir_2024_01"
              value={documentId}
              onChange={(e) => setDocumentId(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-sky-500"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-1.5 rounded-lg text-xs text-slate-400 hover:text-slate-200 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSaving || !name.trim()}
              className="flex items-center gap-1.5 px-4 py-1.5 bg-sky-600 hover:bg-sky-500 text-white rounded-lg text-xs font-medium transition-colors disabled:opacity-50"
            >
              <Plus className="w-3.5 h-3.5" />
              {isSaving ? 'Creating...' : 'Create Watchlist'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
