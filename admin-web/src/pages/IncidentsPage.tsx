import { useState, useEffect } from 'react';
import { 
  AlertTriangle, CheckCircle, Clock, 
  RefreshCw, HardHat, Cpu, FileText, ChevronDown, Wrench, Play, Sparkles
} from 'lucide-react';
import AIInvestigationModal from '../components/AIInvestigationModal';

interface Incident {
  id: string;
  _id?: string;
  incidentCode: string;
  type: string;
  severity: string;
  status: string;
  title: string;
  description: string;
  machineId?: string;
  machineCode?: string;
  machineType?: string;
  operatorId?: string;
  operatorName?: string;
  workOrderId?: string;
  workOrderCode?: string;
  queuedWorkOrders?: string[];
  executionId?: string;
  operationId?: string;
  reportedAt: string;
  detectedAt?: string;
  resolvedAt?: string;
  reportedBy: string;
  resolvedBy?: string;
  resolution?: string;
  dismissalReason?: string;
  maintenanceEstimatedEnd?: string;
  maintenanceDurationMinutes?: number;
}

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [selectedIncidentContext, setSelectedIncidentContext] = useState<any | null>(null);
  const [isContextModalOpen, setIsContextModalOpen] = useState(false);
  const [contextLoading, setContextLoading] = useState(false);
  const [, setNow] = useState<number>(Date.now());

  // Active Dropdown state for card action menus
  const [activeDropdownId, setActiveDropdownId] = useState<string | null>(null);

  // Resolve Modal State
  const [resolveIncidentId, setResolveIncidentId] = useState<string | null>(null);
  const [resolutionText, setResolutionText] = useState('');
  const [isResolveModalOpen, setIsResolveModalOpen] = useState(false);

  // Maintenance Modal State
  const [maintenanceIncidentId, setMaintenanceIncidentId] = useState<string | null>(null);
  const [maintenanceDuration, setMaintenanceDuration] = useState<number>(10);
  const [maintenanceNotes, setMaintenanceNotes] = useState('');
  const [isMaintenanceModalOpen, setIsMaintenanceModalOpen] = useState(false);

  // Dismiss Modal State
  const [dismissIncidentId, setDismissIncidentId] = useState<string | null>(null);
  const [dismissalReasonText, setDismissalReasonText] = useState('');
  const [isDismissModalOpen, setIsDismissModalOpen] = useState(false);

  // AI Operations Modal State
  const [aiIncident, setAiIncident] = useState<{ id: string; code: string } | null>(null);
  const [aiStatus, setAiStatus] = useState<{ aiEnabled: boolean; isSimulationMode: boolean; model: string } | null>(null);
  const [aiToggling, setAiToggling] = useState(false);

  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  // 1-second interval to drive live countdown timers
  useEffect(() => {
    const timer = setInterval(() => {
      setNow(Date.now());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const fetchAiStatus = async () => {
    try {
      const res = await fetch(`${API_URL}/api/ai/status`);
      if (res.ok) {
        const data = await res.json();
        setAiStatus(data);
      }
    } catch (e) {
      console.warn('Could not fetch AI status:', e);
    }
  };

  const toggleAiSimulationMode = async () => {
    setAiToggling(true);
    try {
      const res = await fetch(`${API_URL}/api/ai/simulation-mode`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setAiStatus(data);
      }
    } catch (e) {
      console.error('Failed to toggle AI mode:', e);
    } finally {
      setAiToggling(false);
    }
  };

  const fetchIncidents = async () => {
    try {
      const res = await fetch(`${API_URL}/api/incidents`);
      if (!res.ok) throw new Error('Failed to load incidents');
      const data = await res.json();
      setIncidents(data);
    } catch (err: any) {
      console.warn('Incident fetch warning:', err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIncidents();
    fetchAiStatus();
    const interval = setInterval(() => {
      fetchIncidents();
      fetchAiStatus();
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  // WebSocket Live Incident Subscription
  useEffect(() => {
    const wsUrl = API_URL.replace(/^http/, 'ws') + '/api/ws/execution';
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if ([
          'INCIDENT_CREATED', 'INCIDENT_CONFIRMED', 'INCIDENT_DISMISSED',
          'INCIDENT_RESOLVED', 'INCIDENT_MAINTENANCE_SCHEDULED',
          'MACHINE_FAILED', 'MACHINE_RECOVERED', 'MACHINE_MAINTENANCE_SCHEDULED'
        ].includes(msg.type)) {
          fetchIncidents();
        }
      } catch (err) {
        console.error('WS parse error:', err);
      }
    };

    return () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.close();
      } else if (ws.readyState === WebSocket.CONNECTING) {
        ws.onopen = () => {
          ws.close();
        };
      }
    };
  }, [API_URL]);

  const handleConfirmFailure = async (incId: string) => {
    if (!window.confirm('Confirm that this machine has failed? This will mark the machine as DOWN and attempt automatic failover to available backups.')) return;
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/incidents/${incId}/confirm-failure`, {
        method: 'POST'
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Failed to confirm machine failure');
      }
      await fetchIncidents();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleOpenDismiss = (incId: string) => {
    setDismissIncidentId(incId);
    setDismissalReasonText('Checked machine sensors; evaluated as false alarm');
    setIsDismissModalOpen(true);
  };

  const handleSubmitDismiss = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!dismissIncidentId) return;
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/incidents/${dismissIncidentId}/dismiss`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: dismissalReasonText, dismissedBy: 'ADMIN' })
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Failed to dismiss incident');
      }
      setIsDismissModalOpen(false);
      await fetchIncidents();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleOpenResolve = (incId: string) => {
    setResolveIncidentId(incId);
    setResolutionText('Replaced worn cutting blade and re-calibrated sensors. Machine verified operational.');
    setActiveDropdownId(null);
    setIsResolveModalOpen(true);
  };

  const handleSubmitResolve = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!resolveIncidentId) return;
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/incidents/${resolveIncidentId}/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ resolution: resolutionText, resolvedBy: 'ADMIN' })
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Failed to resolve incident');
      }
      setIsResolveModalOpen(false);
      await fetchIncidents();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleOpenMaintenance = (incId: string) => {
    setMaintenanceIncidentId(incId);
    setMaintenanceDuration(10);
    setMaintenanceNotes('Hydraulic pump seal replacement and sensor recalibration.');
    setActiveDropdownId(null);
    setIsMaintenanceModalOpen(true);
  };

  const handleSubmitMaintenance = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!maintenanceIncidentId) return;
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/incidents/${maintenanceIncidentId}/maintenance`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          durationMinutes: Number(maintenanceDuration),
          resolution: maintenanceNotes,
          adminId: 'ADMIN'
        })
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Failed to schedule maintenance');
      }
      setIsMaintenanceModalOpen(false);
      await fetchIncidents();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleInspectContext = async (incId: string) => {
    setContextLoading(true);
    setIsContextModalOpen(true);
    setSelectedIncidentContext(null);
    try {
      const res = await fetch(`${API_URL}/api/incidents/${incId}`);
      if (!res.ok) throw new Error('Failed to load incident context dossier');
      const data = await res.json();
      setSelectedIncidentContext(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setContextLoading(false);
    }
  };

  const formatCountdown = (isoEndTime?: string) => {
    if (!isoEndTime) return null;
    const diff = new Date(isoEndTime).getTime() - Date.now();
    if (diff <= 0) return 'Timer Expired (Recovering...)';
    const totalSecs = Math.floor(diff / 1000);
    const mins = Math.floor(totalSecs / 60);
    const secs = totalSecs % 60;
    return `${mins.toString().padStart(2, '0')}m ${secs.toString().padStart(2, '0')}s remaining`;
  };

  const filteredIncidents = incidents.filter((inc) => {
    if (statusFilter === 'ALL') return true;
    return inc.status === statusFilter;
  });

  const pendingCount = incidents.filter(i => i.status === 'PENDING_REVIEW').length;
  const actionCount = incidents.filter(i => i.status === 'ACTION_REQUIRED').length;

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'PENDING_REVIEW':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200 animate-pulse">
            <Clock className="w-3.5 h-3.5" />
            PENDING REVIEW
          </span>
        );
      case 'ACTION_REQUIRED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
            <AlertTriangle className="w-3.5 h-3.5 text-rose-600" />
            CONFIRMED DOWN
          </span>
        );
      case 'RESOLVED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle className="w-3.5 h-3.5 text-emerald-600" />
            RESOLVED
          </span>
        );
      case 'DISMISSED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-zinc-100 text-zinc-600 border border-zinc-200">
            DISMISSED
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-zinc-100 text-zinc-700 border border-zinc-200">
            {status}
          </span>
        );
    }
  };

  const getSeverityBadge = (sev: string) => {
    switch (sev) {
      case 'CRITICAL':
        return 'bg-rose-100 text-rose-800 border-rose-300';
      case 'HIGH':
        return 'bg-amber-100 text-amber-800 border-amber-300';
      case 'MEDIUM':
        return 'bg-blue-100 text-blue-800 border-blue-300';
      default:
        return 'bg-zinc-100 text-zinc-700 border-zinc-300';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-900">Incident Triage & Resolution</h1>
          <p className="text-sm text-zinc-500">
            Review operator alerts, confirm machine downtime, schedule maintenance windows with live recovery timers, and inspect telemetry.
          </p>
        </div>
        <div className="flex items-center gap-2.5">
          {/* AI Engine Status & Simulation Toggle */}
          <button
            onClick={toggleAiSimulationMode}
            disabled={aiToggling}
            title={aiStatus?.isSimulationMode ? "AI is in Outage Simulation Mode (using deterministic fallback). Click to activate Live Gemini." : "AI is Live via Gemini. Click to simulate AI outage / deterministic fallback."}
            className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all shadow-2xs cursor-pointer ${
              aiStatus?.isSimulationMode
                ? 'bg-amber-50 border-amber-300 text-amber-900 hover:bg-amber-100'
                : 'bg-white border-zinc-200 text-zinc-800 hover:bg-zinc-50'
            }`}
          >
            <span className="relative flex h-2 w-2">
              <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                aiStatus?.isSimulationMode ? 'bg-amber-400' : 'bg-emerald-400'
              }`}></span>
              <span className={`relative inline-flex rounded-full h-2 w-2 ${
                aiStatus?.isSimulationMode ? 'bg-amber-500' : 'bg-emerald-500'
              }`}></span>
            </span>
            <span className="font-mono text-[11px]">
              {aiStatus?.isSimulationMode ? 'AI: Outage Simulated' : `AI: Live (${aiStatus?.model || 'Gemini'})`}
            </span>
            <span className="text-[10px] px-1.5 py-0.2 rounded font-mono font-normal bg-black/5 border border-black/10">
              {aiStatus?.isSimulationMode ? 'Fallback Active' : 'Online'}
            </span>
          </button>

          <button
            onClick={fetchIncidents}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-zinc-200 rounded-lg text-xs font-semibold text-zinc-700 bg-white hover:bg-zinc-50 transition-colors shadow-2xs cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-sm text-rose-700 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-rose-400 hover:text-rose-600 p-1">
            ✕
          </button>
        </div>
      )}

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 bg-white p-2 rounded-xl border border-zinc-200 shadow-2xs overflow-x-auto">
        {[
          { key: 'ALL', label: 'All Incidents', count: incidents.length },
          { key: 'PENDING_REVIEW', label: 'Pending Review', count: pendingCount, highlight: pendingCount > 0 },
          { key: 'ACTION_REQUIRED', label: 'Confirmed Down', count: actionCount, highlight: actionCount > 0 },
          { key: 'RESOLVED', label: 'Resolved', count: incidents.filter(i => i.status === 'RESOLVED').length },
          { key: 'DISMISSED', label: 'Dismissed', count: incidents.filter(i => i.status === 'DISMISSED').length },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setStatusFilter(tab.key)}
            className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-colors whitespace-nowrap ${
              statusFilter === tab.key
                ? 'bg-zinc-900 text-white font-semibold shadow-2xs'
                : 'text-zinc-600 hover:bg-zinc-100'
            }`}
          >
            <span>{tab.label}</span>
            <span className={`px-1.5 py-0.2 rounded-full text-[10px] font-mono ${
              statusFilter === tab.key 
                ? 'bg-zinc-700 text-white' 
                : tab.highlight 
                  ? 'bg-amber-100 text-amber-800 font-bold' 
                  : 'bg-zinc-200 text-zinc-600'
            }`}>
              {tab.count}
            </span>
          </button>
        ))}
      </div>

      {/* Incidents Grid */}
      {loading ? (
        <div className="text-center py-16 text-zinc-400 text-xs font-mono">Loading factory incidents...</div>
      ) : filteredIncidents.length === 0 ? (
        <div className="text-center py-16 border border-dashed border-zinc-300 rounded-2xl bg-white space-y-1">
          <p className="text-sm font-semibold text-zinc-800">No incidents in this category</p>
          <p className="text-xs text-zinc-400">All workstations operating nominally without reported disruptions.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {filteredIncidents.map((inc) => {
            const incId = inc.id || inc._id || '';
            const isPending = inc.status === 'PENDING_REVIEW';
            const isActionRequired = inc.status === 'ACTION_REQUIRED';
            const isResolved = inc.status === 'RESOLVED';
            const isDismissed = inc.status === 'DISMISSED';
            const isDropdownOpen = activeDropdownId === incId;
            const countdownStr = formatCountdown(inc.maintenanceEstimatedEnd);

            return (
              <div
                key={incId}
                className="bg-white border border-zinc-200 rounded-2xl p-5 shadow-xs hover:shadow-md transition-all flex flex-col justify-between space-y-4 relative"
              >
                <div>
                  <div className="flex items-start justify-between gap-2 border-b border-zinc-100 pb-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-xs text-zinc-900 bg-zinc-100 px-2 py-0.5 rounded border border-zinc-200">
                          {inc.incidentCode}
                        </span>
                        <span className={`px-2 py-0.5 rounded font-mono font-bold text-[10px] border ${getSeverityBadge(inc.severity)}`}>
                          {inc.severity}
                        </span>
                      </div>
                      <h3 className="font-bold text-zinc-900 text-base mt-1.5">{inc.title}</h3>
                    </div>
                    {getStatusBadge(inc.status)}
                  </div>

                  {/* Active Maintenance Timer Banner */}
                  {countdownStr && inc.status !== 'RESOLVED' && inc.status !== 'DISMISSED' && (
                    <div className="mt-3 p-2.5 bg-indigo-50 border border-indigo-200 rounded-xl flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2 text-indigo-900 font-semibold">
                        <Wrench className="w-4 h-4 text-indigo-600 animate-spin" />
                        <span>Maintenance in Progress</span>
                      </div>
                      <span className="font-mono font-bold text-indigo-700 bg-white px-2 py-0.5 rounded border border-indigo-200 shadow-2xs">
                        ⏱ {countdownStr}
                      </span>
                    </div>
                  )}

                  {/* Context Info Box */}
                  <div className="grid grid-cols-2 gap-2 text-xs font-mono bg-zinc-50 p-3 rounded-xl border border-zinc-200/80 my-3">
                    <div>
                      <span className="text-zinc-400 text-[10px] block">Machine:</span>
                      <strong className="text-zinc-900 flex items-center gap-1">
                        <Cpu className="w-3 h-3 text-zinc-600" />
                        {inc.machineCode || 'None'}
                      </strong>
                    </div>
                    <div>
                      <span className="text-zinc-400 text-[10px] block">Reported By:</span>
                      <strong className="text-zinc-900 flex items-center gap-1">
                        <HardHat className="w-3 h-3 text-amber-600" />
                        {inc.operatorName || inc.reportedBy}
                      </strong>
                    </div>
                    <div>
                      <span className="text-zinc-400 text-[10px] block">Work Order(s):</span>
                      <strong className="text-zinc-800 truncate block" title={inc.workOrderCode || inc.queuedWorkOrders?.join(', ')}>
                        {inc.workOrderCode 
                          ? `${inc.workOrderCode}${inc.queuedWorkOrders && inc.queuedWorkOrders.length > 0 ? ` (+${inc.queuedWorkOrders.length} queued)` : ''}`
                          : inc.queuedWorkOrders && inc.queuedWorkOrders.length > 0 
                            ? inc.queuedWorkOrders.join(', ')
                            : 'None'
                        }
                      </strong>
                    </div>
                    <div>
                      <span className="text-zinc-400 text-[10px] block">Operation / Type:</span>
                      <strong className="text-zinc-800">
                        {inc.operationId 
                          ? `${inc.operationId} (${inc.machineType || 'WORKSTATION'})`
                          : inc.machineType 
                            ? `${inc.machineType} Station`
                            : 'None'
                        }
                      </strong>
                    </div>
                  </div>

                  {/* Operator Message Description */}
                  <div className="p-3 bg-white border border-zinc-200 rounded-xl space-y-1">
                    <span className="text-[10px] font-semibold uppercase text-zinc-400 tracking-wider block">
                      Operator Observation / Report:
                    </span>
                    <p className="text-xs text-zinc-800 font-mono italic">
                      &quot;{inc.description}&quot;
                    </p>
                  </div>

                  {/* Resolution Banner */}
                  {isResolved && inc.resolution && (
                    <div className="mt-3 p-3 bg-emerald-50/70 border border-emerald-200 rounded-xl space-y-1">
                      <span className="text-[10px] font-semibold uppercase text-emerald-700 tracking-wider flex items-center gap-1">
                        <CheckCircle className="w-3 h-3 text-emerald-600" />
                        Resolution Recorded ({inc.resolvedBy || 'ADMIN'}):
                      </span>
                      <p className="text-xs text-emerald-900 font-mono">
                        {inc.resolution}
                      </p>
                    </div>
                  )}

                  {/* Dismissal Banner */}
                  {isDismissed && inc.dismissalReason && (
                    <div className="mt-3 p-3 bg-zinc-50 border border-zinc-200 rounded-xl space-y-1">
                      <span className="text-[10px] font-semibold uppercase text-zinc-500 tracking-wider block">
                        Dismissal Reason:
                      </span>
                      <p className="text-xs text-zinc-700 font-mono">
                        {inc.dismissalReason}
                      </p>
                    </div>
                  )}
                </div>

                {/* Footer Actions */}
                <div className="flex items-center justify-between pt-3 border-t border-zinc-100 flex-wrap gap-2">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleInspectContext(incId)}
                      className="inline-flex items-center gap-1.5 text-xs font-semibold text-zinc-700 hover:text-zinc-900 bg-zinc-100 hover:bg-zinc-200 px-3 py-1.5 rounded-lg transition-colors cursor-pointer"
                    >
                      <FileText className="w-3.5 h-3.5" />
                      Deep Dossier
                    </button>

                    <button
                      onClick={() => setAiIncident({ id: incId, code: inc.incidentCode })}
                      className="inline-flex items-center gap-1.5 text-xs font-bold text-cyan-700 hover:text-cyan-900 bg-cyan-50 hover:bg-cyan-100 border border-cyan-200 px-3 py-1.5 rounded-lg transition-all shadow-2xs cursor-pointer hover:shadow-cyan-100"
                    >
                      <Sparkles className="w-3.5 h-3.5 text-cyan-600 animate-pulse" />
                      Investigate with AI
                    </button>
                  </div>

                  <div className="flex items-center gap-2">
                    {isPending && (
                      <>
                        <button
                          onClick={() => handleOpenDismiss(incId)}
                          className="px-3 py-1.5 bg-zinc-100 hover:bg-zinc-200 text-zinc-700 rounded-lg text-xs font-semibold transition-colors"
                        >
                          Dismiss (False Alarm)
                        </button>
                        <button
                          onClick={() => handleConfirmFailure(incId)}
                          className="px-3 py-1.5 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-xs font-semibold transition-colors shadow-2xs"
                        >
                          Confirm Machine Failure
                        </button>
                      </>
                    )}

                    {isActionRequired && (
                      <div className="relative">
                        <button
                          onClick={() => setActiveDropdownId(isDropdownOpen ? null : incId)}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold shadow-2xs transition-colors"
                        >
                          <CheckCircle className="w-3.5 h-3.5" />
                          Resolve / Maintenance
                          <ChevronDown className="w-3 h-3 ml-0.5" />
                        </button>

                        {/* Dropdown Menu */}
                        {isDropdownOpen && (
                          <div className="absolute right-0 bottom-full mb-1 w-56 bg-white border border-zinc-200 rounded-xl shadow-xl z-20 py-1.5">
                            <button
                              onClick={() => handleOpenResolve(incId)}
                              className="w-full text-left px-3 py-2 text-xs font-semibold text-zinc-800 hover:bg-emerald-50 hover:text-emerald-800 flex items-center gap-2"
                            >
                              <Play className="w-3.5 h-3.5 text-emerald-600" />
                              <div>
                                <div>Immediate Recovery</div>
                                <span className="text-[10px] text-zinc-400 font-normal">Resolve & recover to IDLE now</span>
                              </div>
                            </button>

                            <div className="h-px bg-zinc-100 my-1" />

                            <button
                              onClick={() => handleOpenMaintenance(incId)}
                              className="w-full text-left px-3 py-2 text-xs font-semibold text-zinc-800 hover:bg-indigo-50 hover:text-indigo-800 flex items-center gap-2"
                            >
                              <Wrench className="w-3.5 h-3.5 text-indigo-600" />
                              <div>
                                <div>Put in Maintenance</div>
                                <span className="text-[10px] text-zinc-400 font-normal">Set estimated repair timer</span>
                              </div>
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Immediate Resolve Modal */}
      {isResolveModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md border border-zinc-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-zinc-200 bg-zinc-50/50">
              <h2 className="text-base font-bold text-zinc-900 flex items-center gap-2">
                <CheckCircle className="w-5 h-5 text-emerald-600" />
                Resolve Incident & Recover Machine
              </h2>
            </div>
            <form onSubmit={handleSubmitResolve} className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Resolution / Fix Description <span className="text-rose-500">*</span>
                </label>
                <textarea
                  required
                  rows={4}
                  value={resolutionText}
                  onChange={(e) => setResolutionText(e.target.value)}
                  placeholder="Detail the technical repair or corrective action performed..."
                  className="w-full px-3 py-2 border border-zinc-300 rounded-lg text-xs font-mono"
                />
              </div>
              <div className="flex items-center justify-end gap-2 pt-3 border-t border-zinc-100">
                <button
                  type="button"
                  onClick={() => setIsResolveModalOpen(false)}
                  className="px-4 py-2 border border-zinc-200 text-xs font-medium rounded-lg text-zinc-700 hover:bg-zinc-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold shadow-xs"
                >
                  Confirm & Recover to IDLE
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Put in Maintenance Modal */}
      {isMaintenanceModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md border border-zinc-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-zinc-200 bg-zinc-50/50">
              <h2 className="text-base font-bold text-zinc-900 flex items-center gap-2">
                <Wrench className="w-5 h-5 text-indigo-600" />
                Schedule Maintenance & Repair Timer
              </h2>
            </div>
            <form onSubmit={handleSubmitMaintenance} className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Estimated Repair Duration (Minutes) <span className="text-rose-500">*</span>
                </label>
                <div className="grid grid-cols-4 gap-2 mb-2">
                  {[5, 10, 30, 60].map(mins => (
                    <button
                      key={mins}
                      type="button"
                      onClick={() => setMaintenanceDuration(mins)}
                      className={`py-1.5 rounded-lg text-xs font-mono font-bold border transition-colors ${
                        maintenanceDuration === mins 
                          ? 'bg-zinc-900 text-white border-zinc-900' 
                          : 'bg-zinc-50 text-zinc-700 border-zinc-200 hover:bg-zinc-100'
                      }`}
                    >
                      {mins}m
                    </button>
                  ))}
                </div>
                <input
                  type="number"
                  min="1"
                  required
                  value={maintenanceDuration}
                  onChange={(e) => setMaintenanceDuration(Number(e.target.value))}
                  className="w-full px-3 py-2 border border-zinc-300 rounded-lg text-xs font-mono"
                  placeholder="Custom minutes..."
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Maintenance Notes & Action Items
                </label>
                <textarea
                  rows={3}
                  value={maintenanceNotes}
                  onChange={(e) => setMaintenanceNotes(e.target.value)}
                  placeholder="Describe parts being serviced, technician notes, etc."
                  className="w-full px-3 py-2 border border-zinc-300 rounded-lg text-xs font-mono"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-zinc-100">
                <button
                  type="button"
                  onClick={() => setIsMaintenanceModalOpen(false)}
                  className="px-4 py-2 border border-zinc-200 text-xs font-medium rounded-lg text-zinc-700 hover:bg-zinc-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-xs"
                >
                  Start Maintenance Window
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Dismiss Modal */}
      {isDismissModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md border border-zinc-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-zinc-200 bg-zinc-50/50">
              <h2 className="text-base font-bold text-zinc-900">Dismiss Operator Alert</h2>
            </div>
            <form onSubmit={handleSubmitDismiss} className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Dismissal Reason <span className="text-rose-500">*</span>
                </label>
                <textarea
                  required
                  rows={3}
                  value={dismissalReasonText}
                  onChange={(e) => setDismissalReasonText(e.target.value)}
                  className="w-full px-3 py-2 border border-zinc-300 rounded-lg text-xs font-mono"
                />
              </div>
              <div className="flex items-center justify-end gap-2 pt-3 border-t border-zinc-100">
                <button
                  type="button"
                  onClick={() => setIsDismissModalOpen(false)}
                  className="px-4 py-2 border border-zinc-200 text-xs font-medium rounded-lg text-zinc-700 hover:bg-zinc-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-zinc-900 hover:bg-zinc-800 text-white rounded-lg text-xs font-semibold shadow-xs"
                >
                  Dismiss Report
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Deep Dossier Modal */}
      {isContextModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[85vh] overflow-hidden border border-zinc-200 flex flex-col">
            <div className="px-6 py-4 border-b border-zinc-200 bg-zinc-50/50 flex items-center justify-between">
              <div>
                <span className="text-xs font-mono font-bold text-zinc-400 uppercase">Context Dossier</span>
                <h2 className="text-base font-bold text-zinc-900">
                  {selectedIncidentContext?.incident?.incidentCode || 'Incident'} Detailed Context
                </h2>
              </div>
              <button
                onClick={() => setIsContextModalOpen(false)}
                className="text-zinc-400 hover:text-zinc-600 p-1"
              >
                ✕
              </button>
            </div>

            <div className="p-6 overflow-y-auto flex-1 space-y-4">
              {contextLoading ? (
                <div className="text-center py-12 text-zinc-400 text-xs font-mono">
                  Loading deep telemetry & context...
                </div>
              ) : selectedIncidentContext ? (
                <div className="space-y-4 text-xs font-mono">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-3 bg-zinc-50 border border-zinc-200 rounded-xl space-y-1.5">
                      <span className="font-bold text-zinc-700 uppercase text-[10px] block">Machine Telemetry:</span>
                      <div>Code: <strong>{selectedIncidentContext.machine?.machineCode || 'None'}</strong></div>
                      <div>Type: <strong>{selectedIncidentContext.machine?.type || 'None'}</strong></div>
                      <div>Status: <strong>{selectedIncidentContext.machine?.status || 'None'}</strong></div>
                      <div>Location: <strong>{selectedIncidentContext.machine?.location || 'None'}</strong></div>
                    </div>

                    <div className="p-3 bg-zinc-50 border border-zinc-200 rounded-xl space-y-1.5">
                      <span className="font-bold text-zinc-700 uppercase text-[10px] block">Work Order Telemetry:</span>
                      <div>Code: <strong>{selectedIncidentContext.workOrder?.workOrderCode || 'None'}</strong></div>
                      <div>Operation: <strong>{selectedIncidentContext.operation?.operationId || 'None'}</strong> ({selectedIncidentContext.operation?.name})</div>
                      <div>Status: <strong>{selectedIncidentContext.workOrder?.status || 'None'}</strong></div>
                      <div>Batch Qty: <strong>{selectedIncidentContext.workOrder?.quantity || 0} units</strong></div>
                    </div>
                  </div>

                  {selectedIncidentContext.downstreamOperations?.length > 0 && (
                    <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl space-y-1">
                      <span className="font-bold text-rose-800 uppercase text-[10px] block">Downstream Blocked Operations:</span>
                      <div className="flex flex-wrap gap-1 pt-1">
                        {selectedIncidentContext.downstreamOperations.map((d: any) => (
                          <span key={d.operationId} className="px-2 py-0.5 bg-white border border-rose-200 rounded text-rose-700 text-[10px]">
                            {d.operationId} ({d.name})
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="p-3 bg-zinc-50 border border-zinc-200 rounded-xl space-y-2">
                    <span className="font-bold text-zinc-700 uppercase text-[10px] block">Recent Execution Trace Events:</span>
                    <div className="space-y-1 max-h-48 overflow-y-auto text-[11px]">
                      {selectedIncidentContext.recentExecutionEvents?.map((ev: any, idx: number) => (
                        <div key={idx} className="flex justify-between items-center py-1 border-b border-zinc-200/60 last:border-0">
                          <span className="text-zinc-500 font-bold">{ev.eventType}</span>
                          <span className="text-zinc-800">{ev.message}</span>
                          <span className="text-zinc-400 text-[10px]">{new Date(ev.timestamp).toLocaleTimeString()}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center py-12 text-zinc-400 text-xs">No context available.</div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* AI Investigation & Action Planning Modal */}
      {aiIncident && (
        <AIInvestigationModal
          isOpen={!!aiIncident}
          onClose={() => setAiIncident(null)}
          incidentId={aiIncident.id}
          incidentCode={aiIncident.code}
          onSuccess={fetchIncidents}
        />
      )}
    </div>
  );
}
