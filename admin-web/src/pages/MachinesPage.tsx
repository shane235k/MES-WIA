import { useState, useEffect } from 'react';
import { 
  Plus, Edit2, Trash2, X, AlertTriangle, ShieldAlert, 
  Wrench, Play, Clock, Cpu, Sparkles
} from 'lucide-react';
import AIPredictiveMaintenanceModal from '../components/AIPredictiveMaintenanceModal';

interface MachineHealthSummary {
  machineId: string;
  machineCode: string;
  machineName: string;
  machineType: string;
  status: string;
  healthScore: number;
  riskLevel: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  dataQuality: 'INSUFFICIENT_DATA' | 'LIMITED_DATA' | 'SUFFICIENT_DATA' | 'STRONG_HISTORY';
  maintenanceAttention: boolean;
  cycleTimeDeviationPercent: number;
  processingRateEfficiencyPercent: number;
}

interface Machine {
  id?: string;
  _id?: string;
  machineCode: string;
  name: string;
  type: string;
  supportedTypes?: string[];
  status: string;
  capabilityIds: string[];
  location: string;
  availability: boolean;
  processingRate?: number;
  rateUnit?: string;
  color?: string;
  currentOperationId?: string | null;
  currentWorkOrderId?: string | null;
  currentWorkOrderCode?: string | null;
  currentOperatorId?: string | null;
  currentIncidentId?: string | null;
  maintenanceEstimatedEnd?: string;
  maintenanceDurationMinutes?: number;
  maintenanceReason?: string;
}

interface Operator {
  id?: string;
  _id?: string;
  name: string;
  employeeId: string;
}

export const MACHINE_TYPE_COLORS: Record<string, string> = {
  CUTTING: '#3B82F6',       // Blue
  BENDING: '#10B981',       // Emerald
  WELDING: '#F59E0B',       // Amber
  PAINTING: '#EC4899',      // Pink
  INSPECTION: '#06B6D4',    // Cyan
  DRILLING: '#8B5CF6',      // Purple
  MILLING: '#F97316',       // Orange
  STAMPING: '#EF4444',      // Rose
  ASSEMBLY: '#6366F1',      // Indigo
  PACKAGING: '#14B8A6',     // Teal
  MULTI_PURPOSE: '#84CC16', // Lime
};

export const MACHINE_TYPES = [
  'CUTTING',
  'BENDING',
  'WELDING',
  'PAINTING',
  'INSPECTION',
  'DRILLING',
  'MILLING',
  'STAMPING',
  'ASSEMBLY',
  'PACKAGING',
  'MULTI_PURPOSE'
];

export default function MachinesPage() {
  const [machines, setMachines] = useState<Machine[]>([]);
  const [healthMap, setHealthMap] = useState<Record<string, MachineHealthSummary>>({});
  const [operators, setOperators] = useState<Operator[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingMachine, setEditingMachine] = useState<Machine | null>(null);
  const [, setNow] = useState<number>(Date.now());

  // Predictive Maintenance Modal State
  const [selectedPredictiveMachineId, setSelectedPredictiveMachineId] = useState<string | null>(null);

  // Maintenance Modal State
  const [isMaintenanceModalOpen, setIsMaintenanceModalOpen] = useState(false);
  const [maintenanceMachineId, setMaintenanceMachineId] = useState('');
  const [maintenanceDuration, setMaintenanceDuration] = useState(10);
  const [maintenanceReason, setMaintenanceReason] = useState('Routine preventive maintenance');

  // Operator Alert Simulation Modal State
  const [isAlertModalOpen, setIsAlertModalOpen] = useState(false);
  const [selectedOperatorId, setSelectedOperatorId] = useState('');
  const [alertMachineId, setAlertMachineId] = useState('');
  const [alertMessage, setAlertMessage] = useState('Machine stopped working unexpectedly');

  // Form states
  const [machineCode, setMachineCode] = useState('');
  const [name, setName] = useState('');
  const [type, setType] = useState('CUTTING');
  const [supportedTypes, setSupportedTypes] = useState<string[]>([]);
  const [status, setStatus] = useState('IDLE');
  const [location, setLocation] = useState('');
  const [availability, setAvailability] = useState(true);
  const [processingRate, setProcessingRate] = useState<number>(1.0);
  const [rateUnit, setRateUnit] = useState('units/sec');

  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  const fetchData = async () => {
    try {
      const [machRes, userRes, healthRes] = await Promise.all([
        fetch(`${API_URL}/api/machines`),
        fetch(`${API_URL}/api/users/operators`),
        fetch(`${API_URL}/api/predictive-maintenance/machines`)
      ]);
      
      if (!machRes.ok) throw new Error('Failed to load machines');
      
      const machData = await machRes.json();
      const userData = userRes.ok ? await userRes.json() : [];
      
      setMachines(machData);
      setOperators(userData);
      if (userData.length > 0) {
        setSelectedOperatorId(userData[0].employeeId || userData[0].id || userData[0]._id);
      }

      if (healthRes.ok) {
        const healthList: MachineHealthSummary[] = await healthRes.json();
        const map: Record<string, MachineHealthSummary> = {};
        healthList.forEach(h => {
          map[h.machineId] = h;
          map[h.machineCode] = h;
        });
        setHealthMap(map);
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 3000);
    return () => clearInterval(interval);
  }, []);

  // WebSocket updates
  useEffect(() => {
    const wsUrl = API_URL.replace(/^http/, 'ws') + '/api/ws/execution';
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if ([
          'MACHINE_FAILED', 'MACHINE_RECOVERED', 'MACHINE_MAINTENANCE_SCHEDULED',
          'INCIDENT_CREATED', 'INCIDENT_RESOLVED', 'EXECUTION_STATE_UPDATE'
        ].includes(msg.type)) {
          fetchData();
        }
      } catch (err) {
        console.error('WS parse error:', err);
      }
    };

    return () => ws.close();
  }, [API_URL]);

  const handleOpenCreate = () => {
    setEditingMachine(null);
    setMachineCode('');
    setName('');
    setType('CUTTING');
    setSupportedTypes([]);
    setStatus('IDLE');
    setLocation('');
    setAvailability(true);
    setProcessingRate(1.0);
    setRateUnit('units/sec');
    setIsModalOpen(true);
  };

  const handleOpenEdit = (machine: Machine) => {
    setEditingMachine(machine);
    setMachineCode(machine.machineCode);
    setName(machine.name);
    setType(machine.type);
    setSupportedTypes(machine.supportedTypes || []);
    setStatus(machine.status);
    setLocation(machine.location);
    setAvailability(machine.availability);
    setProcessingRate(machine.processingRate || 1.0);
    setRateUnit(machine.rateUnit || 'units/sec');
    setIsModalOpen(true);
  };

  const handleDelete = async (id: string, code: string) => {
    if (!window.confirm(`Are you sure you want to delete machine "${code}"?`)) return;
    setError(null);
    try {
      const response = await fetch(`${API_URL}/api/machines/${id}`, {
        method: 'DELETE',
      });
      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || 'Failed to delete machine');
      }
      fetchData();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleSimulateFailure = async (machineId: string, machineCode: string) => {
    if (!window.confirm(`Simulate confirmed failure for machine ${machineCode}? This will mark it as DOWN and auto-failover active jobs if backups exist.`)) return;
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/machines/${machineId}/fail`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: `Simulated breakdown on ${machineCode}` })
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Failed to simulate machine failure');
      }
      fetchData();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleOpenAlertModal = (machineId: string) => {
    setAlertMachineId(machineId);
    setAlertMessage('Machine stopped working unexpectedly');
    setIsAlertModalOpen(true);
  };

  const handleSubmitAlert = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/operator-alerts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          operatorId: selectedOperatorId,
          machineId: alertMachineId,
          message: alertMessage
        })
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Failed to submit operator alert');
      }
      setIsAlertModalOpen(false);
      fetchData();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleOpenMaintenanceModal = (machineId: string) => {
    setMaintenanceMachineId(machineId);
    setMaintenanceDuration(10);
    setMaintenanceReason('Preventive maintenance & sensor calibration');
    setIsMaintenanceModalOpen(true);
  };

  const handleSubmitMaintenance = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/machines/${maintenanceMachineId}/maintenance?durationMinutes=${maintenanceDuration}&reason=${encodeURIComponent(maintenanceReason)}`, {
        method: 'POST'
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Failed to put machine in maintenance');
      }
      setIsMaintenanceModalOpen(false);
      fetchData();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleRecover = async (machineId: string) => {
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/machines/${machineId}/recover`, {
        method: 'POST'
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Failed to recover machine');
      }
      fetchData();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const derivedColor = MACHINE_TYPE_COLORS[type.toUpperCase()] || '#3B82F6';
    const payload = {
      machineCode,
      name,
      type,
      supportedTypes: type === 'MULTI_PURPOSE' ? supportedTypes : [],
      status,
      capabilityIds: [],
      location,
      availability,
      processingRate: Number(processingRate),
      rateUnit,
      color: derivedColor,
    };

    try {
      const url = editingMachine
        ? `${API_URL}/api/machines/${editingMachine.id || editingMachine._id}`
        : `${API_URL}/api/machines`;
      const method = editingMachine ? 'PUT' : 'POST';

      const response = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || 'Operation failed');
      }

      await fetchData();
      setIsModalOpen(false);
    } catch (err: any) {
      setError(err.message);
    }
  };

  const toggleSupportedType = (t: string) => {
    setSupportedTypes(prev => 
      prev.includes(t) ? prev.filter(item => item !== t) : [...prev, t]
    );
  };

  const formatCountdown = (isoEndTime?: string) => {
    if (!isoEndTime) return null;
    const diff = new Date(isoEndTime).getTime() - Date.now();
    if (diff <= 0) return 'Timer Expired (Recovering...)';
    const totalSecs = Math.floor(diff / 1000);
    const mins = Math.floor(totalSecs / 60);
    const secs = totalSecs % 60;
    return `${mins.toString().padStart(2, '0')}m ${secs.toString().padStart(2, '0')}s`;
  };

  const getStatusBadge = (machine: Machine) => {
    if (machine.status === 'DOWN') {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-100 text-rose-800 border border-rose-300">
          <span className="w-2 h-2 rounded-full bg-rose-600 animate-ping" />
          DOWN
        </span>
      );
    }
    if (machine.status === 'MAINTENANCE') {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-indigo-100 text-indigo-800 border border-indigo-300">
          <Wrench className="w-3 h-3 text-indigo-600 animate-spin" />
          MAINTENANCE
        </span>
      );
    }
    if (machine.status === 'OCCUPIED') {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">
          <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
          OCCUPIED
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
        <span className="w-2 h-2 rounded-full bg-emerald-500" />
        IDLE
      </span>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-900">Workstation Machines</h1>
          <p className="text-sm text-zinc-500">
            Manage factory equipment, multi-purpose units, and monitor maintenance recovery timers.
          </p>
        </div>
        <button
          onClick={handleOpenCreate}
          className="inline-flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium text-white bg-zinc-900 rounded-lg hover:bg-zinc-800 transition-colors shadow-sm"
        >
          <Plus className="w-4 h-4" />
          Add Machine
        </button>
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

      {/* Grid of Machines */}
      {loading ? (
        <div className="flex items-center justify-center p-12 text-zinc-500 text-sm">
          Loading factory machines...
        </div>
      ) : machines.length === 0 ? (
        <div className="p-8 border border-dashed border-zinc-300 rounded-xl text-center text-zinc-500 text-sm">
          No machines configured. Click &quot;Add Machine&quot; to register factory equipment.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {machines.map((machine) => {
            const mId = (machine.id || machine._id) as string;
            const machColor = MACHINE_TYPE_COLORS[machine.type.toUpperCase()] || machine.color || '#3B82F6';
            const countdown = formatCountdown(machine.maintenanceEstimatedEnd);

            return (
              <div
                key={mId}
                className={`bg-white border rounded-2xl p-5 shadow-xs hover:shadow-md transition-all flex flex-col justify-between ${
                  machine.status === 'DOWN' ? 'border-rose-300 bg-rose-50/20' : 
                  machine.status === 'MAINTENANCE' ? 'border-indigo-300 bg-indigo-50/20' : 
                  'border-zinc-200'
                }`}
              >
                <div>
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2.5">
                      <div
                        className="w-4 h-4 rounded-full border border-black/10 shadow-2xs flex-shrink-0"
                        style={{ backgroundColor: machColor }}
                        title={`Type Color: ${machine.type}`}
                      />
                      <div>
                        <span className="text-xs font-mono font-bold text-zinc-400 uppercase tracking-wider">
                          {machine.machineCode}
                        </span>
                        <h3 className="font-bold text-zinc-900 text-base leading-tight">
                          {machine.name}
                        </h3>
                      </div>
                    </div>
                    {getStatusBadge(machine)}
                  </div>

                  {/* Maintenance Countdown Bar */}
                  {machine.status === 'MAINTENANCE' && countdown && (
                    <div className="my-2.5 p-2 bg-indigo-50 border border-indigo-200 rounded-xl flex items-center justify-between text-xs font-mono">
                      <span className="text-indigo-900 font-semibold flex items-center gap-1">
                        <Clock className="w-3 h-3 text-indigo-600" />
                        Online in:
                      </span>
                      <strong className="text-indigo-700 bg-white px-2 py-0.5 rounded border border-indigo-200 shadow-2xs">
                        {countdown}
                      </strong>
                    </div>
                  )}

                  {/* Active Production Work Order Panel */}
                  {(machine.status === 'OCCUPIED' || machine.currentWorkOrderId) && (
                    <div className="my-2.5 p-3 bg-emerald-50/80 border border-emerald-200 rounded-xl space-y-1.5 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] font-bold text-emerald-800 uppercase tracking-wider flex items-center gap-1.5">
                          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                          Active Execution
                        </span>
                        <span className="font-mono font-bold text-emerald-950 px-2 py-0.5 bg-white border border-emerald-200 rounded text-[11px]">
                          {machine.currentWorkOrderCode || (machine.currentWorkOrderId ? `WO-${machine.currentWorkOrderId.slice(-6)}` : 'RUNNING')}
                        </span>
                      </div>
                      <div className="flex items-center justify-between pt-0.5 text-[11px] text-emerald-900">
                        <span>
                          Step: <strong className="font-mono font-bold">{machine.currentOperationId || 'IN_PROGRESS'}</strong>
                        </span>
                        {machine.currentOperatorId && (
                          <span>
                            Operator: <strong className="font-semibold">{
                              operators.find(o => (o.id || o._id) === machine.currentOperatorId || o.employeeId === machine.currentOperatorId)?.name || machine.currentOperatorId
                            }</strong>
                          </span>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Predictive Maintenance Health Score & Risk Pill */}
                  {(() => {
                    const health = healthMap[mId] || healthMap[machine.machineCode];
                    if (!health) return null;
                    const isHighRisk = health.riskLevel === 'HIGH' || health.riskLevel === 'CRITICAL';
                    return (
                      <div className={`my-2 p-2.5 rounded-xl border flex items-center justify-between text-xs ${
                        health.riskLevel === 'CRITICAL'
                          ? 'bg-red-50/80 border-red-200 text-red-900'
                          : health.riskLevel === 'HIGH'
                          ? 'bg-orange-50/80 border-orange-200 text-orange-900'
                          : health.riskLevel === 'MEDIUM'
                          ? 'bg-amber-50/80 border-amber-200 text-amber-900'
                          : 'bg-emerald-50/80 border-emerald-200 text-emerald-900'
                      }`}>
                        <div className="flex items-center gap-2">
                          <div className={`w-7 h-7 rounded-lg flex items-center justify-center font-mono font-bold text-xs ${
                            health.riskLevel === 'CRITICAL'
                              ? 'bg-red-200 text-red-800'
                              : health.riskLevel === 'HIGH'
                              ? 'bg-orange-200 text-orange-800'
                              : health.riskLevel === 'MEDIUM'
                              ? 'bg-amber-200 text-amber-800'
                              : 'bg-emerald-200 text-emerald-800'
                          }`}>
                            {health.healthScore}
                          </div>
                          <div>
                            <div className="flex items-center gap-1.5 font-semibold text-[11px]">
                              <span>Health: {health.healthScore}/100</span>
                              {isHighRisk && <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-ping" />}
                            </div>
                            <span className="text-[10px] text-zinc-500 block">
                              Risk: <strong className="font-bold">{health.riskLevel}</strong>
                              {health.cycleTimeDeviationPercent > 5 && ` (+${health.cycleTimeDeviationPercent}% cycle time)`}
                            </span>
                          </div>
                        </div>

                        <button
                          onClick={() => setSelectedPredictiveMachineId(mId)}
                          className="px-2.5 py-1 bg-white hover:bg-zinc-50 text-indigo-700 hover:text-indigo-800 font-semibold border border-indigo-200 rounded-lg text-[11px] flex items-center gap-1 shadow-2xs transition-colors"
                          title="Open AI Predictive Maintenance Diagnostics"
                        >
                          <Sparkles className="w-3 h-3 text-indigo-600" />
                          <span>AI Check</span>
                        </button>
                      </div>
                    );
                  })()}

                  <div className="space-y-1.5 text-xs text-zinc-600 my-3">
                    <div className="flex justify-between items-center">
                      <span className="text-zinc-400">Type:</span>
                      <span className="font-semibold text-zinc-800 px-2 py-0.5 rounded text-[11px] bg-zinc-100 border border-zinc-200">
                        {machine.type}
                      </span>
                    </div>

                    {machine.type === 'MULTI_PURPOSE' && machine.supportedTypes && machine.supportedTypes.length > 0 && (
                      <div className="pt-1">
                        <span className="text-zinc-400 text-[10px] block mb-1">Supported Functions:</span>
                        <div className="flex flex-wrap gap-1">
                          {machine.supportedTypes.map(st => (
                            <span key={st} className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-lime-50 text-lime-800 border border-lime-200">
                              {st}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="flex justify-between">
                      <span className="text-zinc-400">Location:</span>
                      <span className="font-medium text-zinc-800">{machine.location}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-400">Processing Rate:</span>
                      <span className="font-mono text-zinc-800">
                        {machine.processingRate} {machine.rateUnit || 'units/sec'}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-between gap-2 mt-4 pt-3 border-t border-zinc-100">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {machine.status === 'DOWN' || machine.status === 'MAINTENANCE' ? (
                      <button
                        onClick={() => handleRecover(mId)}
                        className="inline-flex items-center gap-1 px-2.5 py-1 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 rounded-lg text-xs font-semibold transition-colors"
                        title="Recover Machine to IDLE"
                      >
                        <Play className="w-3 h-3 fill-current" />
                        Recover
                      </button>
                    ) : (
                      <>
                        <button
                          onClick={() => handleSimulateFailure(mId, machine.machineCode)}
                          className="inline-flex items-center gap-1 px-2 py-1 bg-rose-50 hover:bg-rose-100 text-rose-700 rounded-lg text-xs font-medium transition-colors"
                          title="Simulate Confirmed Failure"
                        >
                          <ShieldAlert className="w-3 h-3" />
                          Fail
                        </button>
                        <button
                          onClick={() => handleOpenAlertModal(mId)}
                          className="inline-flex items-center gap-1 px-2 py-1 bg-amber-50 hover:bg-amber-100 text-amber-700 rounded-lg text-xs font-medium transition-colors"
                          title="Simulate Operator Alert"
                        >
                          <AlertTriangle className="w-3 h-3" />
                          Alert
                        </button>
                        <button
                          onClick={() => handleOpenMaintenanceModal(mId)}
                          className="inline-flex items-center gap-1 px-2 py-1 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 rounded-lg text-xs font-medium transition-colors"
                          title="Put Machine in Maintenance"
                        >
                          <Wrench className="w-3 h-3" />
                          Maint
                        </button>
                      </>
                    )}
                  </div>

                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => handleOpenEdit(machine)}
                      className="p-1.5 text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100 rounded-md transition-colors"
                      title="Edit Machine"
                    >
                      <Edit2 className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => handleDelete(mId, machine.machineCode)}
                      className="p-1.5 text-zinc-400 hover:text-rose-600 hover:bg-rose-50 rounded-md transition-colors"
                      title="Delete Machine"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Machine Create / Edit Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-hidden border border-zinc-200 flex flex-col">
            <div className="px-6 py-4 border-b border-zinc-200 flex items-center justify-between bg-zinc-50/50">
              <h2 className="text-base font-bold text-zinc-900 flex items-center gap-2">
                <Cpu className="w-5 h-5 text-zinc-700" />
                {editingMachine ? 'Edit Workstation Machine' : 'Add New Machine'}
              </h2>
              <button
                onClick={() => setIsModalOpen(false)}
                className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-600 hover:bg-zinc-100"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="p-6 overflow-y-auto flex-1 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">
                    Machine Code <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={machineCode}
                    onChange={(e) => setMachineCode(e.target.value.toUpperCase())}
                    placeholder="e.g. M-01"
                    className="w-full px-3 py-2 border border-zinc-300 rounded-lg text-xs font-mono uppercase"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">
                    Machine Name <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. CNC Fiber Laser 1"
                    className="w-full px-3 py-2 border border-zinc-300 rounded-lg text-xs font-medium"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">
                    Machine Type <span className="text-rose-500">*</span>
                  </label>
                  <select
                    value={type}
                    onChange={(e) => setType(e.target.value)}
                    className="w-full px-3 py-2 border border-zinc-300 rounded-lg text-xs bg-white font-medium"
                  >
                    {MACHINE_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">
                    Location / Bay <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                    placeholder="e.g. Bay 2 - Sector B"
                    className="w-full px-3 py-2 border border-zinc-300 rounded-lg text-xs"
                  />
                </div>
              </div>

              {/* Multi-Purpose Checkbox Section */}
              {type === 'MULTI_PURPOSE' && (
                <div className="p-3 bg-lime-50/50 border border-lime-200 rounded-xl space-y-2">
                  <label className="block text-xs font-bold text-lime-900">
                    Supported Multi-Purpose Functions (Check all that apply):
                  </label>
                  <div className="grid grid-cols-2 gap-2">
                    {MACHINE_TYPES.filter(t => t !== 'MULTI_PURPOSE').map((st) => (
                      <label key={st} className="flex items-center gap-2 text-xs text-zinc-800 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={supportedTypes.includes(st)}
                          onChange={() => toggleSupportedType(st)}
                          className="rounded border-zinc-300 text-lime-600 focus:ring-lime-500"
                        />
                        <span>{st}</span>
                      </label>
                    ))}
                  </div>
                </div>
              )}

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">
                    Processing Speed
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    min="0.1"
                    required
                    value={processingRate}
                    onChange={(e) => setProcessingRate(Number(e.target.value))}
                    className="w-full px-3 py-2 border border-zinc-300 rounded-lg text-xs font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">Rate Unit</label>
                  <input
                    type="text"
                    value={rateUnit}
                    onChange={(e) => setRateUnit(e.target.value)}
                    className="w-full px-3 py-2 border border-zinc-300 rounded-lg text-xs"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-zinc-100">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 border border-zinc-200 text-xs font-medium rounded-lg text-zinc-700 hover:bg-zinc-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-zinc-900 text-white text-xs font-semibold rounded-lg hover:bg-zinc-800 shadow-xs"
                >
                  {editingMachine ? 'Save Changes' : 'Create Machine'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Machine Maintenance Modal */}
      {isMaintenanceModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md border border-zinc-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-zinc-200 bg-zinc-50/50">
              <h2 className="text-base font-bold text-zinc-900 flex items-center gap-2">
                <Wrench className="w-5 h-5 text-indigo-600" />
                Put Machine in Maintenance
              </h2>
            </div>
            <form onSubmit={handleSubmitMaintenance} className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Scheduled Duration (Minutes) <span className="text-rose-500">*</span>
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
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Maintenance Notes
                </label>
                <textarea
                  rows={3}
                  value={maintenanceReason}
                  onChange={(e) => setMaintenanceReason(e.target.value)}
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
                  Start Maintenance
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Operator Alert Modal */}
      {isAlertModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md border border-zinc-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-zinc-200 bg-zinc-50/50">
              <h2 className="text-base font-bold text-zinc-900">Simulate Operator Alert</h2>
            </div>
            <form onSubmit={handleSubmitAlert} className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Reporting Operator <span className="text-rose-500">*</span>
                </label>
                <select
                  value={selectedOperatorId}
                  onChange={(e) => setSelectedOperatorId(e.target.value)}
                  className="w-full px-3 py-2 border border-zinc-300 rounded-lg text-xs bg-white"
                >
                  {operators.map((op) => (
                    <option key={(op.id || op._id) as string} value={op.employeeId || op.id || op._id}>
                      {op.name} ({op.employeeId})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Observation Message <span className="text-rose-500">*</span>
                </label>
                <textarea
                  required
                  rows={3}
                  value={alertMessage}
                  onChange={(e) => setAlertMessage(e.target.value)}
                  className="w-full px-3 py-2 border border-zinc-300 rounded-lg text-xs font-mono"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-zinc-100">
                <button
                  type="button"
                  onClick={() => setIsAlertModalOpen(false)}
                  className="px-4 py-2 border border-zinc-200 text-xs font-medium rounded-lg text-zinc-700 hover:bg-zinc-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-xs font-semibold shadow-xs"
                >
                  Submit Alert
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* AI Predictive Maintenance Modal */}
      {selectedPredictiveMachineId && (
        <AIPredictiveMaintenanceModal
          machineId={selectedPredictiveMachineId}
          onClose={() => setSelectedPredictiveMachineId(null)}
          onMaintenanceScheduled={fetchData}
        />
      )}
    </div>
  );
}
