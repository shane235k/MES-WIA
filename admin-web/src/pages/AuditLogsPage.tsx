import { useState, useEffect } from 'react';
import { Shield, RefreshCw, Search } from 'lucide-react';

interface AuditEvent {
  id?: string;
  _id?: string;
  timestamp: string;
  actorId: string;
  actorType: string;
  action: string;
  entityType: string;
  entityId: string;
  source: string;
  metadata: any;
}

export default function AuditLogsPage() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterType, setFilterType] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');

  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  const fetchEvents = async () => {
    try {
      const response = await fetch(`${API_URL}/api/audit-events`);
      if (!response.ok) throw new Error('Failed to fetch audit events');
      const data = await response.json();
      setEvents(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEvents();
  }, []);

  const getActionBadge = (action: string) => {
    if (action.includes('COMPLETED')) {
      return 'bg-emerald-50 text-emerald-700 border-emerald-200';
    }
    if (action.includes('STARTED') || action.includes('OCCUPIED')) {
      return 'bg-blue-50 text-blue-700 border-blue-200';
    }
    if (action.includes('WAITING')) {
      return 'bg-amber-50 text-amber-700 border-amber-200';
    }
    if (action.includes('FAILED') || action.includes('DELETED')) {
      return 'bg-rose-50 text-rose-700 border-rose-200';
    }
    return 'bg-zinc-100 text-zinc-700 border-zinc-200';
  };

  const filteredEvents = events.filter((ev) => {
    if (filterType !== 'ALL' && ev.entityType?.toLowerCase() !== filterType.toLowerCase() && ev.action?.toLowerCase() !== filterType.toLowerCase()) {
      if (filterType === 'PROCESS' && !ev.action.includes('OPERATION') && !ev.action.includes('WORK_ORDER') && !ev.action.includes('RESOURCE')) {
        return false;
      }
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchAction = ev.action?.toLowerCase().includes(q);
      const matchActor = ev.actorId?.toLowerCase().includes(q);
      const matchEntity = ev.entityType?.toLowerCase().includes(q) || ev.entityId?.toLowerCase().includes(q);
      const matchMeta = JSON.stringify(ev.metadata || {}).toLowerCase().includes(q);
      return matchAction || matchActor || matchEntity || matchMeta;
    }
    return true;
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-zinc-900">System Audit & Process Trail</h2>
          <p className="text-sm text-zinc-500 mt-0.5">
            Immutable chronological record of all shop-floor executions, workstation transitions, and user actions.
          </p>
        </div>
        <button
          onClick={() => { setLoading(true); fetchEvents(); }}
          className="inline-flex items-center gap-1.5 px-3.5 py-2 border border-zinc-300 hover:bg-zinc-100 text-zinc-700 rounded-lg text-xs font-semibold transition-colors shadow-2xs"
          title="Refresh Log Feed"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh Trail
        </button>
      </div>

      {error && (
        <div className="p-3 border border-rose-200 bg-rose-50/50 rounded-lg text-xs text-rose-600 font-mono">
          Error: {error}
        </div>
      )}

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-white p-3 rounded-xl border border-zinc-200 shadow-2xs">
        <div className="flex items-center gap-1 overflow-x-auto text-xs font-medium">
          {[
            { key: 'ALL', label: 'All Events' },
            { key: 'PROCESS', label: 'Process Executions' },
            { key: 'work_order', label: 'Work Orders' },
            { key: 'machine', label: 'Workstations' },
            { key: 'user', label: 'Users & Operators' },
            { key: 'product', label: 'Products & Recipes' },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setFilterType(tab.key)}
              className={`px-3 py-1.5 rounded-lg transition-colors whitespace-nowrap ${
                filterType === tab.key
                  ? 'bg-zinc-900 text-white font-semibold shadow-2xs'
                  : 'text-zinc-600 hover:bg-zinc-100'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="relative w-full sm:w-64">
          <Search className="w-3.5 h-3.5 text-zinc-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search action, actor, entity..."
            className="w-full pl-8 pr-3 py-1.5 bg-zinc-50 border border-zinc-200 rounded-lg text-xs font-mono focus:bg-white focus:ring-2 focus:ring-zinc-900/10 focus:border-zinc-900"
          />
        </div>
      </div>

      {/* Events List */}
      {loading ? (
        <div className="text-center py-16 text-xs text-zinc-500 font-mono">Loading audit trail records...</div>
      ) : filteredEvents.length === 0 ? (
        <div className="text-center py-16 border border-dashed border-zinc-200 rounded-xl bg-white space-y-1">
          <p className="text-sm font-semibold text-zinc-700">No matching audit records</p>
          <p className="text-xs text-zinc-400">All process operations will be recorded here as they occur.</p>
        </div>
      ) : (
        <div className="border border-zinc-200 rounded-xl bg-white overflow-hidden shadow-2xs divide-y divide-zinc-200">
          {filteredEvents.map((event) => {
            const id = event.id || event._id || '';
            const dateStr = new Date(event.timestamp).toLocaleString();
            return (
              <div key={id} className="p-4 hover:bg-zinc-50/60 transition-colors text-xs flex gap-3.5 items-start">
                <div className="p-2 bg-zinc-100 rounded-lg border border-zinc-200 mt-0.5 text-zinc-600 flex-shrink-0">
                  <Shield className="w-4 h-4" />
                </div>
                
                <div className="flex-1 space-y-1.5">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-0.5 rounded font-mono font-bold text-[11px] border ${getActionBadge(event.action)}`}>
                        {event.action}
                      </span>
                      <span className="font-mono text-zinc-400 text-[10px]">
                        Entity: <strong className="text-zinc-700">{event.entityType}</strong> ({event.entityId})
                      </span>
                    </div>
                    <span className="text-[11px] text-zinc-400 font-mono">{dateStr}</span>
                  </div>

                  <div className="text-zinc-500 font-mono text-[10px] flex flex-wrap gap-x-4 gap-y-1 pt-0.5">
                    <span>Actor: <strong className="text-zinc-800">{event.actorId}</strong> ({event.actorType})</span>
                    <span>Source: <strong className="text-zinc-800">{event.source}</strong></span>
                  </div>

                  {event.metadata && Object.keys(event.metadata).length > 0 && (
                    <pre className="mt-1 text-[10px] font-mono bg-zinc-50 p-2.5 border border-zinc-200 rounded-lg overflow-x-auto text-zinc-700 leading-relaxed">
                      {JSON.stringify(event.metadata, null, 2)}
                    </pre>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
