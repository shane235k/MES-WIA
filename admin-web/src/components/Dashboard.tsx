import { useState, useEffect, useMemo } from 'react';
import { 
  Activity, CheckCircle, 
  RefreshCw, Gauge, 
  ShieldCheck, Zap, Sparkles, AlertTriangle, Clock, ArrowRight
} from 'lucide-react';

interface WorkOrderOperation {
  operationId: string;
  name: string;
  sequence: number;
  assignedMachineId?: string | null;
  assignedOperatorId?: string | null;
  status: string;
  waitingReason?: string | null;
  startedAt?: string | null;
  estimatedCompletionAt?: string | null;
  durationSeconds?: number | null;
  quantityCompleted: number;
  quantityRejected: number;
}

interface WorkOrder {
  id?: string;
  _id?: string;
  workOrderCode: string;
  name?: string;
  productId: string;
  workflowId: string;
  quantity: number;
  priority: string;
  dueDate: string;
  status: string;
  startedAt?: string | null;
  completedAt?: string | null;
  operations: WorkOrderOperation[];
}

interface Product {
  id?: string;
  _id?: string;
  productCode: string;
  name: string;
  description: string;
  unit: string;
  active: boolean;
  recipes?: any[];
}

interface Machine {
  id?: string;
  _id?: string;
  machineCode: string;
  name: string;
  type: string;
  status: string;
  processingRate?: number;
  rateUnit?: string;
  color?: string;
  maintenanceEstimatedEnd?: string;
}

interface User {
  id?: string;
  _id?: string;
  name: string;
  employeeId: string;
  role: string;
  availabilityStatus?: string;
}

interface HealthResponse {
  status: string;
  api: { status: string };
  database: { status: string; latency_ms?: number };
  redis: { status: string; latency_ms?: number };
}

export default function Dashboard() {
  const [workOrders, setWorkOrders] = useState<WorkOrder[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [machines, setMachines] = useState<Machine[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [maintAlerts, setMaintAlerts] = useState<any[]>([]);
  
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<string>('');
  const [now, setNow] = useState<number>(Date.now());

  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  const formatCountdown = (isoEndTime?: string) => {
    if (!isoEndTime) return null;
    const endMs = new Date(isoEndTime).getTime();
    if (isNaN(endMs)) return null;
    const diff = endMs - now;
    if (diff <= 0) return 'Recovering...';
    const totalSecs = Math.floor(diff / 1000);
    const mins = Math.floor(totalSecs / 60);
    const secs = totalSecs % 60;
    return `${mins.toString().padStart(2, '0')}m ${secs.toString().padStart(2, '0')}s`;
  };

  const fetchAllLiveData = async () => {
    try {
      const [woRes, prodRes, machRes, userRes, healthRes, alertsRes] = await Promise.allSettled([
        fetch(`${API_URL}/api/work-orders`),
        fetch(`${API_URL}/api/products`),
        fetch(`${API_URL}/api/machines`),
        fetch(`${API_URL}/api/users`),
        fetch(`${API_URL}/api/health`),
        fetch(`${API_URL}/api/predictive-maintenance/alerts`)
      ]);

      if (woRes.status === 'fulfilled' && woRes.value.ok) setWorkOrders(await woRes.value.json());
      if (prodRes.status === 'fulfilled' && prodRes.value.ok) setProducts(await prodRes.value.json());
      if (machRes.status === 'fulfilled' && machRes.value.ok) {
        const mData = await machRes.value.json();
        setMachines(mData);
      }
      if (userRes.status === 'fulfilled' && userRes.value.ok) setUsers(await userRes.value.json());
      if (healthRes.status === 'fulfilled' && healthRes.value.ok) setHealth(await healthRes.value.json());
      if (alertsRes.status === 'fulfilled' && alertsRes.value.ok) {
        setMaintAlerts(await alertsRes.value.json());
      }

      setLastUpdated(new Date().toLocaleTimeString());
    } catch (err) {
      console.error('Failed to fetch live dashboard telemetry:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAllLiveData();
    const interval = setInterval(fetchAllLiveData, 3000);
    return () => clearInterval(interval);
  }, []);

  // WebSocket real-time event updates
  useEffect(() => {
    const wsUrl = API_URL.replace(/^http/, 'ws') + '/api/ws/execution';
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if ([
          'MACHINE_FAILED', 'MACHINE_RECOVERED', 'MACHINE_MAINTENANCE_SCHEDULED',
          'INCIDENT_CREATED', 'INCIDENT_RESOLVED', 'EXECUTION_STATE_UPDATE',
          'WORK_ORDER_STARTED', 'WORK_ORDER_COMPLETED'
        ].includes(msg.type)) {
          fetchAllLiveData();
        }
      } catch (err) {
        console.error('WS parse error in Dashboard:', err);
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

  // Real MES telemetry calculations (No mock data)
  const metrics = useMemo(() => {
    const completedWos = workOrders.filter(w => w.status === 'COMPLETED');
    const inProgressWos = workOrders.filter(w => w.status === 'IN_PROGRESS');
    const plannedWos = workOrders.filter(w => w.status === 'PLANNED');

    // Total units manufactured
    const totalUnitsManufactured = completedWos.reduce((acc, curr) => acc + (curr.quantity || 0), 0);

    // Theoretical shop-floor capacity (sum of machine processing rates in units/sec)
    const totalCapacityUnitsPerSec = machines.reduce((acc, m) => acc + (m.processingRate || 1.0), 0);
    const capacityUnitsPerHour = totalCapacityUnitsPerSec * 3600;

    // Workstation utilization
    const workingMachines = machines.filter(m => m.status === 'OCCUPIED');
    const machineUtilizationPct = machines.length > 0
      ? Math.round((workingMachines.length / machines.length) * 100)
      : 0;

    // Operators available
    const activeOperators = users.filter(u => u.role === 'OPERATOR');
    const assignedOperators = activeOperators.filter(u => u.availabilityStatus === 'ASSIGNED');
    const operatorUtilizationPct = activeOperators.length > 0
      ? Math.round((assignedOperators.length / activeOperators.length) * 100)
      : 0;

    return {
      completedWosCount: completedWos.length,
      inProgressWosCount: inProgressWos.length,
      plannedWosCount: plannedWos.length,
      totalUnitsManufactured,
      totalCapacityUnitsPerSec: Math.round(totalCapacityUnitsPerSec * 10) / 10,
      capacityUnitsPerHour: Math.round(capacityUnitsPerHour),
      workingMachinesCount: workingMachines.length,
      totalMachinesCount: machines.length,
      machineUtilizationPct,
      activeOperatorsCount: activeOperators.length,
      assignedOperatorsCount: assignedOperators.length,
      operatorUtilizationPct,
      completedWos,
      inProgressWos,
      plannedWos
    };
  }, [workOrders, machines, users]);

  // SVG Semi-Circle Speedometer Gauge Component
  const renderSpeedometer = (pct: number) => {
    const radius = 60;
    const circumference = Math.PI * radius;
    const strokeDashoffset = circumference - (pct / 100) * circumference;

    return (
      <div className="relative flex flex-col items-center justify-center">
        <svg width="150" height="90" viewBox="0 0 150 90" className="overflow-visible">
          {/* Background arc */}
          <path
            d="M 15 80 A 60 60 0 0 1 135 80"
            fill="none"
            stroke="#E4E4E7"
            strokeWidth="12"
            strokeLinecap="round"
          />
          {/* Active progress arc */}
          <path
            d="M 15 80 A 60 60 0 0 1 135 80"
            fill="none"
            stroke="#18181B"
            strokeWidth="12"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            className="transition-all duration-700 ease-out"
          />
        </svg>
        <div className="absolute bottom-0 text-center">
          <span className="text-2xl font-mono font-bold text-zinc-900 tracking-tight">
            {pct}%
          </span>
          <span className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider block">
            Load Factor
          </span>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6 text-zinc-900 pb-12">
      {/* Top Banner & Telemetry Sync Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-5 rounded-2xl border border-zinc-200 shadow-xs">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 bg-zinc-900 rounded-sm" />
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-zinc-400">
              Live Shop-Floor Operations
            </span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-900 mt-1">
            Manufacturing Telemetry & Factory Capacity
          </h1>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-zinc-50 border border-zinc-200 rounded-xl text-xs font-mono">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-zinc-600">Updated {lastUpdated || 'Connecting...'}</span>
          </div>
          <button
            onClick={() => { setLoading(true); fetchAllLiveData(); }}
            className="p-2 border border-zinc-200 hover:bg-zinc-100 rounded-xl text-zinc-600 transition-colors shadow-2xs"
            title="Force refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* 4 Core Primary Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* 1. Completed Workflows & Units */}
        <div className="bg-white p-5 rounded-2xl border border-zinc-200 shadow-xs flex flex-col justify-between space-y-4">
          <div className="flex items-center justify-between text-zinc-400">
            <span className="text-xs font-mono font-semibold uppercase tracking-wider text-zinc-500">
              Manufactured Units
            </span>
            <CheckCircle className="w-4 h-4 text-zinc-900" />
          </div>
          <div>
            <div className="text-3xl font-bold font-mono text-zinc-900 tracking-tight">
              {metrics.totalUnitsManufactured.toLocaleString()}{' '}
              <span className="text-sm font-normal text-zinc-400 font-sans">units</span>
            </div>
            <p className="text-xs text-zinc-500 mt-1 font-medium">
              Across <strong className="text-zinc-800 font-mono">{metrics.completedWosCount}</strong> completed production runs
            </p>
          </div>
        </div>

        {/* 2. Active In-Progress Work Orders */}
        <div className="bg-white p-5 rounded-2xl border border-zinc-200 shadow-xs flex flex-col justify-between space-y-4">
          <div className="flex items-center justify-between text-zinc-400">
            <span className="text-xs font-mono font-semibold uppercase tracking-wider text-zinc-500">
              Active Production Runs
            </span>
            <Activity className="w-4 h-4 text-zinc-900" />
          </div>
          <div>
            <div className="text-3xl font-bold font-mono text-zinc-900 tracking-tight">
              {metrics.inProgressWosCount}{' '}
              <span className="text-sm font-normal text-zinc-400 font-sans">active</span>
            </div>
            <p className="text-xs text-zinc-500 mt-1 font-medium">
              <strong className="text-zinc-800 font-mono">{metrics.plannedWosCount}</strong> scheduled in queue
            </p>
          </div>
        </div>

        {/* 3. Shop-Floor Processing Capacity */}
        <div className="bg-white p-5 rounded-2xl border border-zinc-200 shadow-xs flex flex-col justify-between space-y-4">
          <div className="flex items-center justify-between text-zinc-400">
            <span className="text-xs font-mono font-semibold uppercase tracking-wider text-zinc-500">
              Theoretical Capacity
            </span>
            <Zap className="w-4 h-4 text-zinc-900" />
          </div>
          <div>
            <div className="text-3xl font-bold font-mono text-zinc-900 tracking-tight">
              {metrics.totalCapacityUnitsPerSec}{' '}
              <span className="text-sm font-normal text-zinc-400 font-sans">u/sec</span>
            </div>
            <p className="text-xs text-zinc-500 mt-1 font-medium">
              Max rate: <strong className="text-zinc-800 font-mono">{metrics.capacityUnitsPerHour.toLocaleString()}</strong> units / hour
            </p>
          </div>
        </div>

        {/* 4. Active Machinery Workstation Utilization */}
        <div className="bg-white p-5 rounded-2xl border border-zinc-200 shadow-xs flex flex-col justify-between space-y-4">
          <div className="flex items-center justify-between text-zinc-400">
            <span className="text-xs font-mono font-semibold uppercase tracking-wider text-zinc-500">
              Workstation Utilization
            </span>
            <Gauge className="w-4 h-4 text-zinc-900" />
          </div>
          <div>
            <div className="text-3xl font-bold font-mono text-zinc-900 tracking-tight">
              {metrics.workingMachinesCount} / {metrics.totalMachinesCount}{' '}
              <span className="text-sm font-normal text-zinc-400 font-sans">machines</span>
            </div>
            <p className="text-xs text-zinc-500 mt-1 font-medium">
              <strong className="text-zinc-800 font-mono">{metrics.machineUtilizationPct}%</strong> current shop-floor load
            </p>
          </div>
        </div>
      </div>

      {/* AI Predictive Maintenance Health Status Summary Banner (Monochrome Black & White Vercel Theme) */}
      <div className="bg-black text-white p-5 rounded-2xl border border-zinc-800 shadow-md flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="p-2.5 bg-zinc-900 border border-zinc-800 rounded-xl text-white">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold tracking-wide text-white">
                AI Predictive Machine Health Telemetry
              </h3>
              <span className="text-[10px] px-2 py-0.5 bg-zinc-800 text-zinc-300 border border-zinc-700 rounded-md font-mono">
                Active Analysis
              </span>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              {maintAlerts.length > 0 ? (
                <span>
                  <strong className="text-zinc-200 font-bold">{maintAlerts.length} workstation(s)</strong> exhibit elevated cycle degradation or reliability risk.
                </span>
              ) : (
                <span>All workstations operating within nominal baseline tolerances with healthy reliability ratings.</span>
              )}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {maintAlerts.length > 0 && (
            <div className="flex items-center gap-1.5 px-3 py-1.5 bg-zinc-900 border border-zinc-700 rounded-xl text-zinc-300 text-xs font-mono">
              <AlertTriangle className="w-3.5 h-3.5 text-zinc-400" />
              <span>{maintAlerts.length} Attention Flagged</span>
            </div>
          )}
          <a
            href="/machines"
            className="px-4 py-2 bg-white hover:bg-zinc-200 text-black font-semibold rounded-xl text-xs flex items-center gap-1.5 transition-colors shadow-xs whitespace-nowrap"
          >
            <span>Inspect Machine Health</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </a>
        </div>
      </div>

      {/* Speedometer & Workstation Load Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 items-start">
        {/* Left: Monochromatic Speedometer Load Gauge (Positioned Prominently at Top) */}
        <div className="bg-white p-6 rounded-2xl border border-zinc-200 shadow-xs flex flex-col space-y-4">
          <div>
            <span className="text-xs font-mono font-bold text-zinc-400 uppercase tracking-wider">
              Workstation Utilization Meter
            </span>
            <h3 className="text-base font-bold text-zinc-900 mt-0.5">Real-time Machinery Load</h3>
            <p className="text-xs text-zinc-500 mt-1 leading-relaxed">
              Calculated dynamically from active Work Order execution assignments and workstation occupancy locks.
            </p>
          </div>

          {/* Prominent Top Gauge */}
          <div className="py-2 flex justify-center bg-zinc-50/60 rounded-xl border border-zinc-100 p-4">
            {renderSpeedometer(metrics.machineUtilizationPct)}
          </div>

          <div className="space-y-2 pt-1">
            <div className="flex items-center justify-between text-xs font-mono p-2.5 bg-zinc-50 rounded-lg border border-zinc-200/80">
              <span className="text-zinc-500">Active Workstations:</span>
              <span className="font-bold text-zinc-900">{metrics.workingMachinesCount} of {metrics.totalMachinesCount}</span>
            </div>
            <div className="flex items-center justify-between text-xs font-mono p-2.5 bg-zinc-50 rounded-lg border border-zinc-200/80">
              <span className="text-zinc-500">Shopfloor Status:</span>
              <span className={`font-bold px-2 py-0.5 rounded text-[10px] ${
                metrics.machineUtilizationPct > 0 ? 'bg-emerald-100 text-emerald-800' : 'bg-zinc-200 text-zinc-700'
              }`}>
                {metrics.machineUtilizationPct > 0 ? 'ACTIVE PRODUCTION' : 'STANDBY IDLE'}
              </span>
            </div>
          </div>
        </div>

        {/* Right: Workstation Load Distribution Chart (2 Cols) */}
        <div className="lg:col-span-2 bg-white p-6 rounded-2xl border border-zinc-200 shadow-xs flex flex-col space-y-3">
          <div className="flex items-center justify-between border-b border-zinc-100 pb-3">
            <div>
              <span className="text-xs font-mono font-bold text-zinc-400 uppercase tracking-wider">
                Workstations Registry & Output Rates
              </span>
              <h3 className="text-base font-bold text-zinc-900 mt-0.5">Machine Processing Rates & Status</h3>
            </div>
            <span className="text-xs font-mono text-zinc-500 bg-zinc-100 px-2 py-0.5 rounded border border-zinc-200">
              {machines.length} units
            </span>
          </div>

          <div className="space-y-2.5 max-h-[460px] overflow-y-auto pr-1">
            {machines.length === 0 ? (
              <p className="text-xs text-zinc-400 italic text-center py-8">No workstations registered.</p>
            ) : (
              machines.map((m) => {
                const rate = m.processingRate || 1.0;
                const maxRate = Math.max(...machines.map(x => x.processingRate || 1.0), 3.0);
                const barWidth = Math.round((rate / maxRate) * 100);
                const isOccupied = m.status === 'OCCUPIED';

                return (
                  <div key={m.id || m._id} className="p-3 bg-zinc-50 rounded-xl border border-zinc-200/80 space-y-1.5">
                    <div className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-zinc-900 px-1.5 py-0.5 bg-white border border-zinc-200 rounded">
                          {m.machineCode}
                        </span>
                        <span className="font-semibold text-zinc-800">{m.name}</span>
                        <span className="text-[10px] font-mono text-zinc-400">({m.type})</span>
                      </div>
                      
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-zinc-800 text-xs">{rate} u/s</span>
                        {m.status === 'MAINTENANCE' && m.maintenanceEstimatedEnd ? (
                          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-zinc-100 text-zinc-900 border border-zinc-300 flex items-center gap-1">
                            <Clock className="w-3 h-3 text-zinc-600" />
                            <span>MAINT: {formatCountdown(m.maintenanceEstimatedEnd)}</span>
                          </span>
                        ) : (
                          <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${
                            isOccupied 
                              ? 'bg-zinc-900 text-white border-zinc-900 animate-pulse'
                              : 'bg-white text-zinc-600 border-zinc-200'
                          }`}>
                            {m.status}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Monochromatic output rate indicator bar */}
                    <div className="w-full bg-zinc-200 h-1.5 rounded-full overflow-hidden">
                      <div 
                        className="bg-zinc-900 h-full transition-all duration-500"
                        style={{ width: `${barWidth}%` }}
                      />
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      {/* Currently Manufactured Products Specs & Active Runs */}
      <div className="bg-white p-6 rounded-2xl border border-zinc-200 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-zinc-100 pb-3">
          <div>
            <span className="text-xs font-mono font-bold text-zinc-400 uppercase tracking-wider">
              Shop-Floor Execution Active Runs
            </span>
            <h3 className="text-base font-bold text-zinc-900">Current Product Production & Specs</h3>
          </div>
          <span className="text-xs font-mono font-medium text-zinc-500">
            {metrics.inProgressWos.length} active runs in execution
          </span>
        </div>

        {metrics.inProgressWos.length === 0 ? (
          <div className="text-center py-12 border border-dashed border-zinc-200 rounded-xl space-y-1">
            <p className="text-sm font-semibold text-zinc-700">No active work orders running</p>
            <p className="text-xs text-zinc-400">Schedule and start a work order from the Work Orders tab to see real-time specs.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {metrics.inProgressWos.map((wo) => {
              const prod = products.find(p => (p.id || p._id) === wo.productId);
              const activeOps = (wo.operations || []).filter(o => o.status === 'IN_PROGRESS');
              const completedOpsCount = (wo.operations || []).filter(o => o.status === 'COMPLETED').length;
              const totalOps = (wo.operations || []).length;

              return (
                <div key={wo.id || wo._id} className="p-4 bg-zinc-50 rounded-xl border border-zinc-200/90 space-y-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-1.5">
                        <span className="font-mono font-bold text-xs px-2 py-0.5 bg-white border border-zinc-200 rounded text-zinc-900">
                          {wo.workOrderCode}
                        </span>
                        {wo.name && <span className="text-xs font-semibold text-zinc-800">• {wo.name}</span>}
                      </div>
                      <h4 className="font-bold text-zinc-900 text-sm mt-1">
                        {prod ? prod.name : 'Custom Product'}
                      </h4>
                      <p className="text-xs text-zinc-500 font-mono mt-0.5">
                        Product Code: <strong className="text-zinc-700">{prod?.productCode || wo.productId}</strong>
                      </p>
                    </div>

                    <span className="px-2 py-0.5 bg-blue-50 text-blue-700 border border-blue-200 rounded text-xs font-semibold font-mono animate-pulse">
                      IN PRODUCTION
                    </span>
                  </div>

                  <p className="text-xs text-zinc-600 line-clamp-2">
                    {prod?.description || 'Structural manufacturing component specification.'}
                  </p>

                  <div className="grid grid-cols-2 gap-2 text-xs bg-white p-2.5 rounded-lg border border-zinc-200 font-mono">
                    <div>
                      <span className="text-zinc-400 text-[10px] block">Target Quantity</span>
                      <strong className="text-zinc-900">{wo.quantity} {prod?.unit || 'pcs'}</strong>
                    </div>
                    <div>
                      <span className="text-zinc-400 text-[10px] block">Steps Progress</span>
                      <strong className="text-zinc-900">{completedOpsCount} / {totalOps} finished</strong>
                    </div>
                  </div>

                  {activeOps.length > 0 && (
                    <div className="pt-2 border-t border-zinc-200/60 space-y-1">
                      <span className="text-[10px] font-semibold uppercase text-zinc-500 tracking-wider">
                        Executing Operations:
                      </span>
                      {activeOps.map(op => (
                        <div key={op.operationId} className="flex items-center justify-between text-xs bg-white p-2 rounded-lg border border-zinc-200">
                          <div className="flex items-center gap-1.5">
                            <span className="font-mono font-bold text-zinc-800">{op.operationId}</span>
                            <span className="text-zinc-900 font-medium">{op.name}</span>
                          </div>
                          <span className="font-mono font-bold text-blue-700 text-xs">
                            {op.durationSeconds ? `${op.durationSeconds}s cycle` : 'Running'}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Production Queue & Next Product Recommendation */}
      <div className="bg-white p-6 rounded-2xl border border-zinc-200 shadow-xs space-y-4">
        <div>
          <span className="text-xs font-mono font-bold text-zinc-400 uppercase tracking-wider">
            Product Catalog & Cycle Time Estimations
          </span>
          <h3 className="text-base font-bold text-zinc-900">What Should Be Manufactured Next?</h3>
          <p className="text-xs text-zinc-500 mt-1">
            Product recipes ready in catalog with estimated cycle durations and resource readiness.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {products.map((p) => {
            const recipe = p.recipes?.[0];
            const stepCount = recipe?.steps?.length || 0;
            const avgDurationSeconds = stepCount > 0 ? stepCount * 8 : 20;

            return (
              <div key={p.id || p._id} className="p-4 bg-zinc-50 rounded-xl border border-zinc-200 flex flex-col justify-between space-y-3">
                <div>
                  <div className="flex items-start justify-between">
                    <div>
                      <span className="text-xs font-mono font-bold text-zinc-400 uppercase">
                        {p.productCode}
                      </span>
                      <h4 className="font-bold text-zinc-900 text-sm">{p.name}</h4>
                    </div>
                    <span className="text-xs font-mono font-semibold px-2 py-0.5 bg-white border border-zinc-200 rounded text-zinc-800">
                      {p.unit}
                    </span>
                  </div>

                  <p className="text-xs text-zinc-500 line-clamp-2 my-2">{p.description || 'Standard catalog specification'}</p>

                  <div className="space-y-1.5 text-xs text-zinc-600 bg-white p-3 rounded-lg border border-zinc-200 font-mono">
                    <div className="flex justify-between">
                      <span className="text-zinc-400">Active Recipe:</span>
                      <span className="font-bold text-zinc-900">{recipe ? recipe.recipeName : 'None'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-400">Step Routing:</span>
                      <span>{stepCount} Operations</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-400">Est. 10-Unit Cycle:</span>
                      <span className="font-bold text-zinc-900">{avgDurationSeconds} seconds</span>
                    </div>
                  </div>
                </div>

                <div className="pt-2 border-t border-zinc-200/60 flex items-center justify-between text-xs">
                  <span className="text-emerald-700 font-semibold flex items-center gap-1">
                    <ShieldCheck className="w-3.5 h-3.5" />
                    Ready for Production
                  </span>
                  <span className="font-mono text-zinc-400 text-[10px]">
                    v{recipe?.version || 1}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Infrastructure Node Health */}
      {health && (
        <div className="bg-white p-5 rounded-2xl border border-zinc-200 shadow-xs flex flex-wrap items-center justify-between gap-4 font-mono text-xs">
          <div className="flex items-center gap-2">
            <span className="font-bold text-zinc-900 uppercase">Core Systems Status:</span>
            <span className="px-2 py-0.5 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded text-[11px] font-bold">
              {health.status.toUpperCase()}
            </span>
          </div>

          <div className="flex items-center gap-6 text-zinc-500 text-[11px]">
            <span>FastAPI: <strong className="text-zinc-800">{health.api.status}</strong></span>
            <span>MongoDB: <strong className="text-zinc-800">{health.database.status}</strong> ({health.database.latency_ms || 1}ms)</span>
            <span>Redis: <strong className="text-zinc-800">{health.redis.status}</strong> ({health.redis.latency_ms || 1}ms)</span>
          </div>
        </div>
      )}
    </div>
  );
}
