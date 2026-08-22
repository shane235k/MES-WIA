import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { 
  ReactFlow, 
  Background, 
  Controls, 
  MiniMap, 
  useNodesState, 
  useEdgesState, 
  Handle, 
  Position, 
  MarkerType 
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { 
  ArrowLeft, Play, Pause, Cog, 
  CheckCircle, Clock, AlertCircle, AlertTriangle, Radio, Terminal, HardHat,
  Cpu, X, RefreshCw, Box
} from 'lucide-react';
import { extractErrorMessage } from '../utils/apiError';

// Custom Node component displaying Name on Top, Machine Color accents, Operator pills, dynamic countdowns, and clear halt/blockage reasons
function OperationNode({ data }: any) {
  const machineColor = data.machineColor || '#3B82F6';
  const status = data.status || 'PENDING';
  const remainingSeconds = data.remainingSeconds ?? data.estimatedDurationSeconds ?? 0;
  
  const isRunning = status === 'IN_PROGRESS';
  const isWaitingResource = status === 'WAITING_FOR_RESOURCE';
  const isWaitingMaterial = status === 'WAITING_FOR_MATERIAL';
  const isCompleted = status === 'COMPLETED';
  const isReady = status === 'READY';
  const isInterrupted = status === 'INTERRUPTED';
  const isPaused = status === 'PAUSED';
  const isFailed = status === 'FAILED';
  const isPending = status === 'PENDING';

  const isMachineDown = data.machineStatus === 'DOWN' || data.machineStatus === 'MAINTENANCE' || (data.waitingReason && (data.waitingReason.includes('DOWN') || data.waitingReason.includes('MAINTENANCE')));
  const isOperatorIssue = data.waitingReason && (data.waitingReason.toLowerCase().includes('operator') || data.waitingReason.toLowerCase().includes('offline') || data.waitingReason.toLowerCase().includes('assigned'));

  // Determine dynamic node border color
  let borderColor = '#E4E4E7';
  let borderLeftColor = machineColor;

  if (isInterrupted || isFailed || isMachineDown) {
    borderColor = '#EF4444';
    borderLeftColor = '#EF4444';
  } else if (isPaused || isWaitingMaterial || isWaitingResource) {
    borderColor = '#F59E0B';
    borderLeftColor = '#F59E0B';
  } else if (isRunning) {
    borderColor = machineColor;
    borderLeftColor = machineColor;
  } else if (isReady) {
    borderColor = '#6366F1';
    borderLeftColor = '#6366F1';
  } else if (isCompleted) {
    borderColor = '#10B981';
    borderLeftColor = '#10B981';
  }

  return (
    <div 
      className="bg-white rounded-xl shadow-md border text-xs w-80 font-sans select-none overflow-hidden transition-all duration-200"
      style={{ 
        borderColor,
        borderLeftWidth: '6px',
        borderLeftColor
      }}
    >
      <Handle type="target" position={Position.Top} className="w-2.5 h-2.5 bg-zinc-400 border-2 border-white" />
      
      {/* Header bar: Operation Name Prominently on Top */}
      <div className="flex justify-between items-center px-3.5 py-2.5 border-b border-zinc-100 bg-zinc-50/70">
        <div className="flex items-center gap-1.5 flex-1 min-w-0 pr-2">
          <span className="font-bold text-zinc-950 text-xs truncate" title={data.name}>
            {data.name}
          </span>
        </div>

        {/* Machine Badge */}
        <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full border shadow-2xs flex-shrink-0 ${
          isMachineDown ? 'bg-rose-50 border-rose-200 text-rose-700 font-bold' : 'bg-white border-zinc-200 text-zinc-800'
        }`}>
          <span 
            className="w-2 h-2 rounded-full flex-shrink-0"
            style={{ backgroundColor: isMachineDown ? '#EF4444' : machineColor }}
          />
          <span className="font-mono font-semibold text-[10px]">
            {isMachineDown ? `${data.machineCode || 'M-??'} ● DOWN` : (data.machineCode || data.requiredMachineType || 'M-??')}
          </span>
        </div>
      </div>

      {/* Body Content */}
      <div className="p-3.5 space-y-2">
        <div className="flex items-center justify-between text-xs text-zinc-500 font-mono">
          <span className="font-bold text-zinc-700 bg-zinc-100 px-1.5 py-0.5 rounded">
            {data.operationId}
          </span>
          <span className="text-[10px] text-zinc-400">
            Seq #{data.sequence}
          </span>
        </div>

        {/* Assigned Operator & Machine Rate */}
        <div className="flex items-center justify-between text-[11px] text-zinc-500 pt-1 border-t border-zinc-100">
          <span className="flex items-center gap-1">
            <HardHat className={`w-3 h-3 flex-shrink-0 ${isOperatorIssue ? 'text-rose-600' : 'text-amber-600'}`} />
            <span className={`truncate max-w-[130px] font-medium ${isOperatorIssue ? 'text-rose-700 font-bold' : 'text-zinc-700'}`}>
              {data.operatorName || (isOperatorIssue ? 'No Operator Assigned' : 'Unassigned')}
            </span>
          </span>
          <span className="font-mono text-zinc-600 font-bold text-[10px] bg-zinc-100 px-1.5 py-0.5 rounded">
            {data.processingRate ? `${data.processingRate} u/s` : '1.0 u/s'}
          </span>
        </div>

        {/* Quantity Flow Metrics (Input -> Output -> Duration) */}
        <div className="bg-zinc-50 border border-zinc-200/90 rounded-lg p-2 grid grid-cols-3 gap-1 text-center font-mono">
          <div>
            <span className="text-[9px] uppercase tracking-wider text-zinc-400 block">Input</span>
            <span className="text-[11px] font-bold text-zinc-800">{data.inputQuantity ?? data.quantity ?? 10} u</span>
          </div>
          <div>
            <span className="text-[9px] uppercase tracking-wider text-zinc-400 block">Output</span>
            <span className="text-[11px] font-bold text-emerald-700">
              {isCompleted ? (data.outputQuantity ?? data.inputQuantity ?? 10) : '-'}
            </span>
          </div>
          <div>
            <span className="text-[9px] uppercase tracking-wider text-zinc-400 block">Duration</span>
            <span className="text-[11px] font-bold text-indigo-700">{data.durationSeconds || data.estimatedDurationSeconds || 5}s</span>
          </div>
        </div>

        {/* Material Requirements & Consumption */}
        {data.requiredMaterials && data.requiredMaterials.length > 0 ? (
          <div className="bg-zinc-50 border border-zinc-200/80 rounded-lg p-2 space-y-1 font-mono text-[10px]">
            <div className="text-[9px] font-bold uppercase tracking-wider text-zinc-400 flex items-center justify-between mb-0.5">
              <span className="flex items-center gap-1">
                <Box className="w-2.5 h-2.5 text-zinc-500" />
                Raw Material Input
              </span>
              <span>Consumed / Req</span>
            </div>
            {data.requiredMaterials.map((rm: any, rmIdx: number) => {
              const reqQty = rm.totalRequiredQuantity ?? rm.quantity ?? 0;
              const consQty = rm.quantityConsumed ?? 0;
              const isConsumed = consQty >= reqQty && reqQty > 0;
              return (
                <div key={rmIdx} className="flex items-center justify-between">
                  <span className="text-zinc-700 truncate max-w-[130px] font-medium" title={rm.materialName}>
                    {rm.materialName || 'Raw Material'}
                    <span className="text-zinc-400 text-[9px] ml-1">({rm.quantityPerUnit || 1}/unit)</span>
                  </span>
                  <span className={`font-bold ${isConsumed ? 'text-emerald-700' : 'text-zinc-800'}`}>
                    {consQty}/{reqQty} {rm.unit || 'units'}
                  </span>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="bg-zinc-50/60 border border-dashed border-zinc-200 rounded-lg py-1 px-2 text-center text-[10px] text-zinc-500 font-mono">
            Material-free process (0 raw material input)
          </div>
        )}

        {/* Live Execution Status & Action Controls */}
        <div className="pt-2 border-t border-zinc-100 space-y-2">
          
          {/* 1. WAITING FOR MATERIAL */}
          {isWaitingMaterial && (
            <div className="bg-amber-50/95 border border-amber-300 rounded-lg p-2.5 space-y-2 text-amber-950">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1.5 font-bold text-[11px] text-amber-900">
                  <Box className="w-3.5 h-3.5 text-amber-700 animate-pulse flex-shrink-0" />
                  MATERIAL CLEARANCE PENDING
                </span>
                <span className="px-1.5 py-0.5 rounded text-[9px] font-mono font-bold bg-amber-200 text-amber-900">
                  WAITING MAT
                </span>
              </div>
              <div className="bg-white/90 rounded p-1.5 border border-amber-200 text-[10px] text-amber-900 font-mono leading-tight">
                <span className="font-semibold block text-[9px] text-amber-700 uppercase tracking-wide">Block Reason:</span>
                {data.waitingReason || 'Awaiting lot inspection clearance or material stock allocation.'}
              </div>
              <div className="flex items-center gap-1.5 pt-1">
                {data.onResumeNode && data.workOrderId && (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      data.onResumeNode(data);
                    }}
                    className="flex-1 py-1.5 px-2 bg-amber-600 hover:bg-amber-700 active:scale-98 text-white rounded-md text-[11px] font-semibold flex items-center justify-center gap-1.5 shadow-xs transition-colors cursor-pointer"
                    title="Check material availability and resume"
                  >
                    <Play className="w-3 h-3 fill-current" />
                    <span>Re-check & Resume</span>
                  </button>
                )}
                {data.onPauseNode && data.workOrderId && (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      data.onPauseNode(data.operationId);
                    }}
                    className="py-1.5 px-2 bg-white hover:bg-zinc-100 text-zinc-700 rounded-md text-[11px] font-medium border border-zinc-200 transition-colors cursor-pointer"
                    title="Pause node"
                  >
                    <Pause className="w-3 h-3 text-zinc-600" />
                  </button>
                )}
              </div>
            </div>
          )}

          {/* 2. WAITING FOR RESOURCE (Machine Down or Operator Missing/Offline) */}
          {isWaitingResource && (
            <div className={`border rounded-lg p-2.5 space-y-2 ${isMachineDown ? 'bg-rose-50/95 border-rose-300 text-rose-950' : 'bg-amber-50/95 border-amber-300 text-amber-950'}`}>
              <div className="flex items-center justify-between">
                <span className={`flex items-center gap-1.5 font-bold text-[11px] ${isMachineDown ? 'text-rose-800' : 'text-amber-900'}`}>
                  {isMachineDown ? (
                    <AlertTriangle className="w-3.5 h-3.5 text-rose-600 animate-bounce flex-shrink-0" />
                  ) : isOperatorIssue ? (
                    <HardHat className="w-3.5 h-3.5 text-amber-700 animate-pulse flex-shrink-0" />
                  ) : (
                    <Clock className="w-3.5 h-3.5 text-amber-700 animate-pulse flex-shrink-0" />
                  )}
                  {isMachineDown ? 'BLOCKED: MACHINE DOWN' : isOperatorIssue ? 'WAITING FOR OPERATOR' : 'WAITING FOR MACHINE'}
                </span>
                <span className={`px-1.5 py-0.5 rounded text-[9px] font-mono font-bold ${isMachineDown ? 'bg-rose-200 text-rose-900' : 'bg-amber-200 text-amber-900'}`}>
                  {isMachineDown ? 'DOWN' : 'WAITING'}
                </span>
              </div>
              <div className={`rounded p-1.5 border text-[10px] font-mono leading-tight ${isMachineDown ? 'bg-white/90 border-rose-200 text-rose-900' : 'bg-white/90 border-amber-200 text-amber-900'}`}>
                <span className="font-semibold block text-[9px] uppercase tracking-wide opacity-75">Halt Reason:</span>
                {data.waitingReason || (isMachineDown ? `Machine ${data.machineCode || ''} is currently DOWN or in maintenance.` : 'Waiting for resource availability...')}
              </div>
              <div className="flex items-center gap-1.5 pt-1">
                {data.onResumeNode && data.workOrderId && (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      data.onResumeNode(data);
                    }}
                    className={`flex-1 py-1.5 px-2 text-white rounded-md text-[11px] font-semibold flex items-center justify-center gap-1.5 shadow-xs transition-colors cursor-pointer ${isMachineDown ? 'bg-rose-600 hover:bg-rose-700' : 'bg-amber-600 hover:bg-amber-700'}`}
                  >
                    <Play className="w-3 h-3 fill-current" />
                    <span>{isMachineDown ? 'Reroute to Backup Machine' : 'Reassign & Resume'}</span>
                  </button>
                )}
                {data.onPauseNode && data.workOrderId && (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      data.onPauseNode(data.operationId);
                    }}
                    className="py-1.5 px-2 bg-white hover:bg-zinc-100 text-zinc-700 rounded-md text-[11px] font-medium border border-zinc-200 transition-colors cursor-pointer"
                    title="Pause node"
                  >
                    <Pause className="w-3 h-3 text-zinc-600" />
                  </button>
                )}
              </div>
            </div>
          )}

          {/* 3. PAUSED */}
          {isPaused && (
            <div className="bg-amber-50/95 border border-amber-300 rounded-lg p-2.5 space-y-2 text-amber-950">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1.5 font-bold text-[11px] text-amber-900">
                  <Pause className="w-3.5 h-3.5 text-amber-700 flex-shrink-0" />
                  OPERATION PAUSED / HALTED
                </span>
                <span className="px-1.5 py-0.5 rounded text-[9px] font-mono font-bold bg-amber-200 text-amber-900">
                  PAUSED
                </span>
              </div>
              <div className="bg-white/90 rounded p-1.5 border border-amber-200 text-[10px] text-amber-900 font-mono leading-tight">
                <span className="font-semibold block text-[9px] text-amber-700 uppercase tracking-wide">Pause Reason:</span>
                {data.waitingReason || 'Halted by administrator or AI orchestration recovery plan.'}
              </div>
              {data.onResumeNode && data.workOrderId && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    data.onResumeNode(data);
                  }}
                  className="w-full py-1.5 px-2 bg-emerald-600 hover:bg-emerald-700 active:scale-98 text-white rounded-md text-[11px] font-semibold flex items-center justify-center gap-1.5 shadow-xs transition-colors cursor-pointer"
                >
                  <Play className="w-3 h-3 fill-current" />
                  <span>Resume Operation Node</span>
                </button>
              )}
            </div>
          )}

          {/* 4. INTERRUPTED OR FAILED */}
          {(isInterrupted || isFailed) && (
            <div className="bg-rose-50/95 border border-rose-300 rounded-lg p-2.5 space-y-2 text-rose-950">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1.5 font-bold text-[11px] text-rose-800">
                  <AlertTriangle className="w-3.5 h-3.5 text-rose-600 flex-shrink-0" />
                  {isFailed ? 'OPERATION FAILED' : 'OPERATION INTERRUPTED'}
                </span>
                <span className="px-1.5 py-0.5 rounded text-[9px] font-mono font-bold bg-rose-200 text-rose-900">
                  {isFailed ? 'FAILED' : 'INTERRUPTED'}
                </span>
              </div>
              <div className="bg-white/90 rounded p-1.5 border border-rose-200 text-[10px] text-rose-900 font-mono leading-tight">
                <span className="font-semibold block text-[9px] text-rose-700 uppercase tracking-wide">Breakdown Details:</span>
                {data.waitingReason || 'Machine failure or breakdown during execution.'}
              </div>
              {data.onResumeNode && data.workOrderId && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    data.onResumeNode(data);
                  }}
                  className="w-full py-1.5 px-2 bg-rose-600 hover:bg-rose-700 active:scale-98 text-white rounded-md text-[11px] font-semibold flex items-center justify-center gap-1.5 shadow-xs transition-colors cursor-pointer"
                >
                  <Play className="w-3 h-3 fill-current" />
                  <span>Resume & Reroute to Backup</span>
                </button>
              )}
            </div>
          )}

          {/* 5. IN PROGRESS (RUNNING) */}
          {isRunning && (
            <div className="bg-blue-50/95 border border-blue-200 rounded-lg p-2.5 space-y-2 text-blue-950 animate-pulse">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1.5 text-blue-700 font-bold text-[11px]">
                  <Cog className="w-3.5 h-3.5 animate-spin text-blue-600" />
                  IN PROGRESS
                </span>
                <span className="font-mono font-bold text-blue-900 text-xs bg-blue-100 px-1.5 py-0.5 rounded">
                  {remainingSeconds}s left
                </span>
              </div>
              <div className="w-full bg-blue-200/60 h-1.5 rounded-full overflow-hidden">
                <div 
                  className="bg-blue-600 h-full transition-all duration-1000"
                  style={{ width: `${Math.max(5, Math.min(100, 100 - (remainingSeconds / (data.durationSeconds || data.estimatedDurationSeconds || 10)) * 100))}%` }}
                />
              </div>
              {data.onPauseNode && data.workOrderId && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    data.onPauseNode(data.operationId);
                  }}
                  className="w-full py-1 px-2 bg-white hover:bg-amber-50 text-amber-800 hover:text-amber-900 border border-amber-300 rounded-md text-[10px] font-semibold flex items-center justify-center gap-1 shadow-2xs transition-colors cursor-pointer"
                >
                  <Pause className="w-2.5 h-2.5 text-amber-600" />
                  <span>Pause Node</span>
                </button>
              )}
            </div>
          )}

          {/* 6. READY */}
          {isReady && (
            <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-2.5 space-y-2 text-indigo-950">
              <div className="flex items-center justify-between text-[11px] font-bold text-indigo-700">
                <span className="flex items-center gap-1.5">
                  <Play className="w-3.5 h-3.5 fill-current text-indigo-600" />
                  READY TO START
                </span>
                <span className="text-[10px] text-indigo-500 font-mono font-bold bg-indigo-100 px-1.5 py-0.5 rounded">
                  Ready
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                {data.onResumeNode && data.workOrderId && (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      data.onResumeNode(data);
                    }}
                    className="flex-1 py-1.5 px-2 bg-indigo-600 hover:bg-indigo-700 active:scale-98 text-white rounded-md text-[11px] font-semibold flex items-center justify-center gap-1.5 shadow-xs transition-colors cursor-pointer"
                  >
                    <Play className="w-3 h-3 fill-current" />
                    <span>Start Operation</span>
                  </button>
                )}
                {data.onPauseNode && data.workOrderId && (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      data.onPauseNode(data.operationId);
                    }}
                    className="py-1.5 px-2 bg-white hover:bg-zinc-100 text-zinc-700 rounded-md text-[11px] font-medium border border-zinc-200 transition-colors cursor-pointer"
                    title="Pause node"
                  >
                    <Pause className="w-3 h-3 text-zinc-600" />
                  </button>
                )}
              </div>
            </div>
          )}

          {/* 7. COMPLETED */}
          {isCompleted && (
            <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-2 flex items-center justify-between text-emerald-800 font-semibold text-[11px]">
              <span className="flex items-center gap-1.5">
                <CheckCircle className="w-3.5 h-3.5 text-emerald-600" />
                COMPLETED
              </span>
              <span className="text-[10px] font-mono text-emerald-600">
                {data.outputQuantity ?? data.inputQuantity ?? 10} units done
              </span>
            </div>
          )}

          {/* 8. PENDING */}
          {isPending && (
            <div className="bg-zinc-100 border border-zinc-200 rounded-lg p-2 text-zinc-600 text-[10px] flex items-center justify-between">
              <span className="flex items-center gap-1.5 font-medium">
                <Clock className="w-3.5 h-3.5 text-zinc-400" />
                PENDING PREDECESSOR
              </span>
              <span className="font-mono text-zinc-500 bg-white px-1.5 py-0.5 rounded border border-zinc-200">
                {data.dependencies?.length > 0 ? data.dependencies.join(', ') : 'Initial Step'}
              </span>
            </div>
          )}

        </div>
      </div>

      <Handle type="source" position={Position.Bottom} className="w-2.5 h-2.5 bg-zinc-400 border-2 border-white" />
    </div>
  );
}

interface Workflow {
  id?: string;
  _id?: string;
  workflowCode: string;
  name: string;
  productId: string;
  version: number;
  status: string;
  operations: any[];
}

interface WorkOrder {
  id?: string;
  _id?: string;
  workOrderCode: string;
  name?: string;
  status: string;
  quantity: number;
  workflowId: string;
}

interface ExecutionEvent {
  _id: string;
  workOrderId?: string;
  eventType: string;
  message: string;
  timestamp: string;
  operationId?: string;
  machineCode?: string;
  operatorName?: string;
}

interface Props {
  workflowId: string;
  initialWorkOrderId?: string;
  onBack: () => void;
}

export default function WorkflowDesignerPage({ workflowId, initialWorkOrderId, onBack }: Props) {
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [workOrders, setWorkOrders] = useState<WorkOrder[]>([]);
  const [selectedWorkOrderId, setSelectedWorkOrderId] = useState<string>(initialWorkOrderId || '');
  const [executionEvents, setExecutionEvents] = useState<ExecutionEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [wsConnected, setWsConnected] = useState(false);

  // React Flow states
  const [nodes, setNodes, onNodesChange] = useNodesState<any>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<any>([]);
  
  const logContainerRef = useRef<HTMLDivElement>(null);
  const nodeTypes = useMemo(() => ({ operationNode: OperationNode }), []);
  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  const [resumeModalOp, setResumeModalOp] = useState<any | null>(null);
  const [allMachines, setAllMachines] = useState<any[]>([]);
  const [allOperators, setAllOperators] = useState<any[]>([]);
  const [selectedMachineId, setSelectedMachineId] = useState<string>('AUTO');
  const [selectedOperatorId, setSelectedOperatorId] = useState<string>('AUTO');
  const [resuming, setResuming] = useState<boolean>(false);

  // Open resume modal handler
  const handleOpenResumeModal = useCallback(async (op: any) => {
    setResumeModalOp(op);
    setSelectedMachineId(op.assignedMachineId || 'AUTO');
    setSelectedOperatorId(op.assignedOperatorId || 'AUTO');

    try {
      const [mRes, uRes] = await Promise.all([
        fetch(`${API_URL}/api/machines`),
        fetch(`${API_URL}/api/users`)
      ]);
      if (mRes.ok) {
        const mData = await mRes.json();
        setAllMachines(mData);
      }
      if (uRes.ok) {
        const uData = await uRes.json();
        setAllOperators(uData.filter((u: any) => u.role === 'OPERATOR'));
      }
    } catch (err) {
      console.error('Error fetching resources for resume:', err);
    }
  }, [API_URL]);

  // Pause node handler
  const handlePauseNode = useCallback(async (opId: string) => {
    if (!selectedWorkOrderId) return;
    try {
      const res = await fetch(`${API_URL}/api/work-orders/${selectedWorkOrderId}/operations/${opId}/pause`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: 'Admin paused operation node' })
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Failed to pause operation');
      }
      // Trigger execution state refresh
      const stateRes = await fetch(`${API_URL}/api/work-orders/${selectedWorkOrderId}/execution-state`);
      if (stateRes.ok) {
        const data = await stateRes.json();
        const stateMap: Record<string, any> = {};
        (data.operations || []).forEach((op: any) => {
          stateMap[op.operationId] = op;
        });
        updateNodeDataInPlace(stateMap);
      }
    } catch (err: any) {
      setError(err.message);
    }
  }, [API_URL, selectedWorkOrderId]);

  // Update existing node data in-place without unmounting/re-positioning nodes
  const updateNodeDataInPlace = useCallback((opsStateMap: Record<string, any>) => {
    setNodes((prevNodes) =>
      prevNodes.map((node) => {
        const liveState = opsStateMap[node.id];
        if (!liveState) {
          return {
            ...node,
            data: {
              ...node.data,
              workOrderId: selectedWorkOrderId,
              onPauseNode: handlePauseNode,
              onResumeNode: handleOpenResumeModal
            }
          };
        }
        return {
          ...node,
          data: {
            ...node.data,
            ...liveState,
            workOrderId: selectedWorkOrderId,
            onPauseNode: handlePauseNode,
            onResumeNode: handleOpenResumeModal
          }
        };
      })
    );

    setEdges((prevEdges) =>
      prevEdges.map((edge) => {
        const targetState = opsStateMap[edge.target];
        const isRunning = targetState?.status === 'IN_PROGRESS';
        return {
          ...edge,
          animated: isRunning,
          style: { stroke: isRunning ? '#3B82F6' : '#94A3B8', strokeWidth: 2 },
          markerEnd: { type: MarkerType.ArrowClosed, color: isRunning ? '#3B82F6' : '#94A3B8' }
        };
      })
    );
  }, [setNodes, setEdges, selectedWorkOrderId, handlePauseNode, handleOpenResumeModal]);

  // Sync execution state for the selected work order
  const syncExecutionState = useCallback(async (woId: string) => {
    if (!woId) return;
    try {
      const res = await fetch(`${API_URL}/api/work-orders/${woId}/execution-state`);
      if (res.ok) {
        const data = await res.json();
        const stateMap: Record<string, any> = {};
        (data.operations || []).forEach((op: any) => {
          stateMap[op.operationId] = op;
        });

        // In-place node update to prevent disappearing/flickering
        updateNodeDataInPlace(stateMap);

        if (data.events) {
          // FIFO: Earliest event on top, latest event at bottom
          const sorted = [...data.events].sort(
            (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
          );
          setExecutionEvents(sorted);
        }
      }
    } catch (err) {
      console.error('Error syncing execution state:', err);
    }
  }, [API_URL, updateNodeDataInPlace]);

  // Confirm resume handler
  const handleConfirmResume = async () => {
    if (!selectedWorkOrderId || !resumeModalOp) return;
    setResuming(true);
    try {
      const res = await fetch(`${API_URL}/api/work-orders/${selectedWorkOrderId}/operations/${resumeModalOp.operationId}/resume`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          machineId: selectedMachineId === 'AUTO' ? null : selectedMachineId,
          operatorId: selectedOperatorId === 'AUTO' ? null : selectedOperatorId
        })
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(extractErrorMessage(errData, 'Failed to resume operation'));
      }
      setResumeModalOp(null);
      await syncExecutionState(selectedWorkOrderId);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setResuming(false);
    }
  };

  // Build DAG node positions once when workflow loads
  // Build DAG node positions once when workflow loads
  const initGraphElements = useCallback((wf: Workflow, opsStateMap: Record<string, any> = {}, usersMap: Record<string, any> = {}, machinesMap: Record<string, any> = {}) => {
    const ops = wf.operations || [];
    const newNodes: any[] = [];
    const newEdges: any[] = [];

    const depthMap: Record<string, number> = {};
    ops.forEach((op, idx) => {
      depthMap[op.operationId] = idx;
    });

    const levelCounts: Record<number, number> = {};

    ops.forEach((op) => {
      const liveState = opsStateMap[op.operationId] || {};
      const level = op.dependencies && op.dependencies.length > 0
        ? Math.max(...op.dependencies.map((d: string) => (depthMap[d] ?? -1) + 1), 0)
        : 0;

      const colIndex = levelCounts[level] || 0;
      levelCounts[level] = colIndex + 1;

      const x = 50 + colIndex * 320;
      const y = 50 + level * 230;

      const opUserId = liveState.assignedOperatorId || op.assignedOperatorId;
      const operObj = opUserId ? usersMap[opUserId] : null;
      const opMachId = liveState.assignedMachineId || op.assignedMachineId;
      const machObj = opMachId ? machinesMap[opMachId] : null;

      newNodes.push({
        id: op.operationId,
        type: 'operationNode',
        position: { x, y },
        data: {
          ...op,
          ...liveState,
          operatorName: liveState.operatorName || (operObj ? operObj.name : undefined),
          operatorEmployeeId: liveState.operatorEmployeeId || (operObj ? operObj.employeeId : undefined),
          machineCode: liveState.machineCode || (machObj ? machObj.machineCode : undefined),
          operationId: op.operationId,
          name: op.name,
          sequence: op.sequence,
          workOrderId: selectedWorkOrderId,
          onPauseNode: handlePauseNode,
          onResumeNode: handleOpenResumeModal
        }
      });

      if (op.dependencies) {
        op.dependencies.forEach((depId: string) => {
          newEdges.push({
            id: `e-${depId}-${op.operationId}`,
            source: depId,
            target: op.operationId,
            animated: liveState.status === 'IN_PROGRESS',
            style: { stroke: liveState.status === 'IN_PROGRESS' ? '#3B82F6' : '#94A3B8', strokeWidth: 2 },
            markerEnd: { type: MarkerType.ArrowClosed, color: liveState.status === 'IN_PROGRESS' ? '#3B82F6' : '#94A3B8' }
          });
        });
      }
    });

    setNodes(newNodes);
    setEdges(newEdges);
  }, [setNodes, setEdges, selectedWorkOrderId, handlePauseNode, handleOpenResumeModal]);

  // Fetch initial workflow & work orders
  const fetchData = useCallback(async () => {
    try {
      const [wfRes, woRes, uRes, mRes] = await Promise.all([
        fetch(`${API_URL}/api/workflows/${workflowId}`),
        fetch(`${API_URL}/api/work-orders`),
        fetch(`${API_URL}/api/users`),
        fetch(`${API_URL}/api/machines`)
      ]);

      if (!wfRes.ok) throw new Error('Failed to load workflow');
      const wfData: Workflow = await wfRes.json();
      const woData: WorkOrder[] = await woRes.json();
      const uData = uRes.ok ? await uRes.json() : [];
      const mData = mRes.ok ? await mRes.json() : [];

      const uMap: Record<string, any> = {};
      uData.forEach((u: any) => {
        const uid = u.id || u._id;
        if (uid) uMap[uid] = u;
      });

      const mMap: Record<string, any> = {};
      mData.forEach((m: any) => {
        const mid = m.id || m._id;
        if (mid) mMap[mid] = m;
      });

      setWorkflow(wfData);
      
      const relatedWos = woData.filter((w: any) => w.workflowId === workflowId);
      setWorkOrders(relatedWos);

      let targetWoId = selectedWorkOrderId;
      if (!targetWoId && relatedWos.length > 0) {
        targetWoId = (relatedWos[0].id || relatedWos[0]._id || '') as string;
        setSelectedWorkOrderId(targetWoId);
      }

      initGraphElements(wfData, {}, uMap, mMap);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [workflowId, API_URL, selectedWorkOrderId, initGraphElements]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    if (selectedWorkOrderId) {
      syncExecutionState(selectedWorkOrderId);
    }
  }, [selectedWorkOrderId, syncExecutionState]);

  // Live WebSocket Connection: strictly filter events for currently selected Work Order (FIFO)
  useEffect(() => {
    const wsUrl = (API_URL.replace(/^http/, 'ws')) + '/api/ws/execution';
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setWsConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'EXECUTION_EVENT') {
          // Strictly display logs for current work order only, append to bottom (FIFO)
          if (selectedWorkOrderId && msg.data.workOrderId === selectedWorkOrderId) {
            setExecutionEvents((prev) => [...prev, msg.data]);
            syncExecutionState(selectedWorkOrderId);
          }
        } else if (msg.type === 'EXECUTION_STATE_UPDATE') {
          if (selectedWorkOrderId && msg.data.workOrderId === selectedWorkOrderId) {
            const stateMap: Record<string, any> = {};
            (msg.data.operations || []).forEach((op: any) => {
              stateMap[op.operationId] = op;
            });
            updateNodeDataInPlace(stateMap);
          }
        } else if (
          msg.type === 'MATERIAL_RESERVED' ||
          msg.type === 'MATERIAL_CONSUMED' ||
          msg.type === 'MATERIAL_RELEASED' ||
          msg.type === 'MATERIAL_SCRAPPED'
        ) {
          if (selectedWorkOrderId && msg.data?.workOrderId === selectedWorkOrderId) {
            setExecutionEvents((prev) => [
              ...prev,
              {
                _id: `mat-${Date.now()}-${Math.random()}`,
                workOrderId: msg.data.workOrderId,
                eventType: msg.type,
                message: msg.type === 'MATERIAL_RESERVED'
                  ? `Material lots reserved for ${msg.data.workOrderCode}`
                  : msg.type === 'MATERIAL_CONSUMED'
                  ? `Materials consumed in Operation ${msg.data.operationId}`
                  : `Material event: ${msg.type}`,
                timestamp: new Date().toISOString()
              }
            ]);
            syncExecutionState(selectedWorkOrderId);
          }
        }
      } catch (err) {
        console.error('WS message error:', err);
      }
    };

    ws.onclose = () => {
      setWsConnected(false);
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
  }, [API_URL, selectedWorkOrderId, syncExecutionState, updateNodeDataInPlace]);

  // Auto-scroll to bottom of log stream whenever new FIFO events arrive
  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [executionEvents]);

  // Periodic 1-second sync tick
  useEffect(() => {
    const interval = setInterval(() => {
      if (selectedWorkOrderId) {
        syncExecutionState(selectedWorkOrderId);
      }
    }, 1000);
    return () => clearInterval(interval);
  }, [selectedWorkOrderId, syncExecutionState]);

  // Start Production Trigger
  const handleStartProduction = async () => {
    if (!selectedWorkOrderId) return;
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/work-orders/${selectedWorkOrderId}/start`, {
        method: 'POST'
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Failed to start execution');
      }
      await syncExecutionState(selectedWorkOrderId);
      await fetchData();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const getEventBadge = (eventType: string) => {
    switch (eventType) {
      case 'WORK_ORDER_STARTED':
      case 'WORK_ORDER_COMPLETED':
        return 'bg-emerald-50 text-emerald-700 border-emerald-200';
      case 'OPERATION_STARTED':
      case 'OPERATION_COMPLETED':
        return 'bg-blue-50 text-blue-700 border-blue-200';
      case 'MACHINE_OCCUPIED':
      case 'MACHINE_RELEASED':
        return 'bg-purple-50 text-purple-700 border-purple-200';
      case 'OPERATOR_ASSIGNED':
      case 'OPERATOR_RELEASED':
        return 'bg-amber-50 text-amber-700 border-amber-200';
      case 'RESOURCE_WAITING':
        return 'bg-rose-50 text-rose-700 border-rose-200';
      case 'MATERIAL_RESERVED':
        return 'bg-indigo-50 text-indigo-700 border-indigo-200 font-bold';
      case 'MATERIAL_CONSUMED':
        return 'bg-emerald-50 text-emerald-700 border-emerald-200 font-bold';
      case 'MATERIAL_RELEASED':
        return 'bg-zinc-100 text-zinc-700 border-zinc-300';
      case 'MATERIAL_SCRAPPED':
        return 'bg-rose-50 text-rose-700 border-rose-200 font-bold';
      default:
        return 'bg-zinc-100 text-zinc-700 border-zinc-200';
    }
  };

  const currentWo = workOrders.find(w => (w.id || w._id) === selectedWorkOrderId);
  const isAllOpsCompleted = currentWo?.status === 'COMPLETED';

  if (loading) {
    return (
      <div className="flex items-center justify-center p-20 text-sm text-zinc-500">
        Loading interactive workflow canvas...
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-6rem)] space-y-3">
      {/* Top Navbar Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-4 rounded-xl border border-zinc-200 shadow-xs">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="p-1.5 border border-zinc-200 hover:bg-zinc-100 rounded-lg text-zinc-600 transition-colors"
            title="Back to Workflows"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono font-bold text-xs text-zinc-500 uppercase">
                {workflow?.workflowCode}
              </span>
              <span className={`text-xs px-2 py-0.5 rounded font-medium border ${
                isAllOpsCompleted 
                  ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                  : 'bg-zinc-100 text-zinc-700 border-zinc-200'
              }`}>
                v{workflow?.version} • {isAllOpsCompleted ? 'COMPLETED' : workflow?.status}
              </span>
              <span className="inline-flex items-center gap-1 text-[11px] text-zinc-500">
                <Radio className={`w-3 h-3 ${wsConnected ? 'text-emerald-500 animate-pulse' : 'text-zinc-300'}`} />
                {wsConnected ? 'Live WebSocket' : 'Connecting...'}
              </span>
            </div>
            <h1 className="text-lg font-bold text-zinc-900">{workflow?.name}</h1>
          </div>
        </div>

        {/* Work Order Execution Trigger Bar */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <span className="text-xs font-semibold text-zinc-600">Active Order:</span>
            <select
              value={selectedWorkOrderId}
              onChange={(e) => setSelectedWorkOrderId(e.target.value)}
              className="px-2.5 py-1.5 border border-zinc-300 rounded-lg text-xs bg-white font-mono font-medium text-zinc-800 focus:ring-2 focus:ring-zinc-900/10 focus:border-zinc-900"
            >
              {workOrders.length === 0 && <option value="">No Work Orders scheduled</option>}
              {workOrders.map((wo) => {
                const woId = (wo.id || wo._id) as string;
                return (
                  <option key={woId} value={woId}>
                    {wo.workOrderCode} {wo.name ? `— ${wo.name}` : ''} ({wo.status})
                  </option>
                );
              })}
            </select>
          </div>

          {currentWo && currentWo.status === 'PLANNED' && (
            <button
              onClick={handleStartProduction}
              className="inline-flex items-center gap-1.5 px-4 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold shadow-xs transition-colors"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              Start Production
            </button>
          )}

          {currentWo && currentWo.status === 'IN_PROGRESS' && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-50 text-blue-700 border border-blue-200 rounded-lg text-xs font-semibold animate-pulse">
              <Cog className="w-3.5 h-3.5 animate-spin text-blue-600" />
              Production Active
            </span>
          )}

          {currentWo && currentWo.status === 'COMPLETED' && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-lg text-xs font-semibold">
              <CheckCircle className="w-3.5 h-3.5 text-emerald-600" />
              Completed
            </span>
          )}
        </div>
      </div>

      {error && (
        <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-700 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Main Split View: Flow Canvas on Left + Light-Themed FIFO Real-Time Execution Logs on Right */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-3 min-h-0">
        {/* Left: React Flow Execution Canvas (2 Cols) */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-zinc-200 overflow-hidden shadow-xs relative">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={nodeTypes}
            fitView
            minZoom={0.2}
            maxZoom={1.5}
          >
            <Background gap={16} size={1} color="#E4E4E7" />
            <Controls className="bg-white border-zinc-200 shadow-sm" />
            <MiniMap 
              nodeStrokeColor="#A1A1AA"
              nodeColor="#F4F4F5"
              className="bg-white border-zinc-200 rounded-lg shadow-sm" 
            />
          </ReactFlow>
        </div>

        {/* Right: Light-Themed FIFO Real-time Execution Event Stream Log Window (1 Col) */}
        <div className="bg-white rounded-xl border border-zinc-200 text-zinc-900 flex flex-col shadow-xs overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-200 bg-zinc-50/70">
            <div className="flex items-center gap-2">
              <Terminal className="w-4 h-4 text-zinc-700" />
              <h3 className="text-xs font-mono font-bold tracking-wider text-zinc-800 uppercase">
                Execution Stream (FIFO) • {currentWo?.workOrderCode || 'None'}
              </h3>
            </div>
            <span className="text-[10px] font-mono text-zinc-600 bg-zinc-100 px-2 py-0.5 rounded border border-zinc-200">
              {executionEvents.length} events
            </span>
          </div>

          {/* FIFO Event Log Stream (Light Theme, Earliest at top, Latest at bottom) */}
          <div 
            ref={logContainerRef}
            className="flex-1 p-3 space-y-2 overflow-y-auto font-mono text-xs max-h-[calc(100vh-14rem)] bg-zinc-50/30"
          >
            {executionEvents.length === 0 ? (
              <div className="text-zinc-400 text-center py-16 text-xs italic">
                No events recorded for this order yet.
              </div>
            ) : (
              executionEvents.map((ev, index) => (
                <div 
                  key={ev._id || index} 
                  className="p-2.5 rounded-lg bg-white border border-zinc-200/90 shadow-2xs space-y-1 hover:border-zinc-300 transition-colors"
                >
                  <div className="flex items-center justify-between text-[10px]">
                    <span className={`px-1.5 py-0.5 rounded font-bold border text-[9px] ${getEventBadge(ev.eventType)}`}>
                      {ev.eventType}
                    </span>
                    <span className="text-zinc-400 font-mono text-[10px]">
                      {new Date(ev.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                  <div className="text-zinc-800 text-[11px] leading-relaxed">
                    {ev.message}
                  </div>
                  {(ev.machineCode || ev.operatorName) && (
                    <div className="text-[10px] text-zinc-500 flex items-center gap-2 pt-1 border-t border-zinc-100">
                      {ev.machineCode && <span>Workstation: <strong className="text-zinc-700 font-semibold">{ev.machineCode}</strong></span>}
                      {ev.operatorName && <span>Operator: <strong className="text-zinc-700 font-semibold">{ev.operatorName}</strong></span>}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Resume Operation Node Modal */}
      {resumeModalOp && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs animate-fadeIn">
          <div className="bg-white border border-zinc-200 rounded-2xl w-full max-w-lg shadow-2xl overflow-hidden flex flex-col">
            
            {/* Header */}
            <div className="px-6 py-4 border-b border-zinc-100 flex items-center justify-between bg-zinc-50/50">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-emerald-600 flex items-center justify-center text-white shadow-xs">
                  <Play className="w-4 h-4 fill-current" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-zinc-900">
                    Resume Operation Node
                  </h3>
                  <p className="text-xs text-zinc-500 font-mono mt-0.5">
                    {resumeModalOp.operationId} — {resumeModalOp.name}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setResumeModalOp(null)}
                className="p-1.5 text-zinc-400 hover:text-zinc-700 bg-zinc-100 hover:bg-zinc-200 rounded-lg transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Body */}
            <div className="p-6 space-y-4 text-xs overflow-y-auto max-h-[70vh]">
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-amber-900 space-y-1">
                <div className="flex items-center gap-1.5 font-semibold text-amber-800">
                  <AlertTriangle className="w-3.5 h-3.5" />
                  <span>Resume Allocation Strategy</span>
                </div>
                <p className="text-[11px] text-amber-800 leading-relaxed">
                  Choose which machine and operator will execute this operation, or leave as Auto-Assign to allocate the first available compatible resource.
                </p>
              </div>

              {/* Machine Selection */}
              <div className="space-y-2">
                <label className="block text-xs font-semibold text-zinc-800">
                  Target Workstation / Machine:
                </label>
                <div className="space-y-1.5 max-h-40 overflow-y-auto pr-1">
                  <label className={`flex items-center justify-between p-2.5 rounded-lg border cursor-pointer transition-colors ${
                    selectedMachineId === 'AUTO' ? 'bg-zinc-900 text-white border-zinc-900' : 'bg-white border-zinc-200 text-zinc-700 hover:bg-zinc-50'
                  }`}>
                    <div className="flex items-center gap-2">
                      <input
                        type="radio"
                        name="machineSelection"
                        checked={selectedMachineId === 'AUTO'}
                        onChange={() => setSelectedMachineId('AUTO')}
                        className="hidden"
                      />
                      <Cpu className="w-4 h-4 opacity-70" />
                      <span className="font-semibold">Auto-Assign Compatible Machine</span>
                    </div>
                    <span className={`text-[10px] font-mono px-2 py-0.5 rounded ${
                      selectedMachineId === 'AUTO' ? 'bg-zinc-800 text-zinc-200' : 'bg-zinc-100 text-zinc-600'
                    }`}>
                      {resumeModalOp.requiredMachineType || 'ANY'}
                    </span>
                  </label>

                  {allMachines.map((m) => {
                    const mId = m.id || m._id;
                    const isSelected = selectedMachineId === mId;
                    const isIdle = m.status === 'IDLE';
                    return (
                      <label 
                        key={mId}
                        className={`flex items-center justify-between p-2.5 rounded-lg border cursor-pointer transition-colors ${
                          isSelected ? 'bg-zinc-900 text-white border-zinc-900' : 'bg-white border-zinc-200 text-zinc-700 hover:bg-zinc-50'
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <input
                            type="radio"
                            name="machineSelection"
                            checked={isSelected}
                            onChange={() => setSelectedMachineId(mId)}
                            className="hidden"
                          />
                          <span className="font-mono font-bold">{m.machineCode}</span>
                          <span className="text-xs">{m.name}</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
                            isSelected ? 'bg-zinc-800 text-zinc-200' : 'bg-zinc-100 text-zinc-600'
                          }`}>
                            {m.type}
                          </span>
                          <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                            isIdle ? 'bg-emerald-100 text-emerald-800' : 'bg-zinc-200 text-zinc-700'
                          }`}>
                            {m.status}
                          </span>
                        </div>
                      </label>
                    );
                  })}
                </div>
              </div>

              {/* Operator Selection */}
              <div className="space-y-2 pt-2 border-t border-zinc-100">
                <label className="block text-xs font-semibold text-zinc-800">
                  Assigned Operator:
                </label>
                <div className="space-y-1.5 max-h-36 overflow-y-auto pr-1">
                  <label className={`flex items-center justify-between p-2.5 rounded-lg border cursor-pointer transition-colors ${
                    selectedOperatorId === 'AUTO' ? 'bg-zinc-900 text-white border-zinc-900' : 'bg-white border-zinc-200 text-zinc-700 hover:bg-zinc-50'
                  }`}>
                    <div className="flex items-center gap-2">
                      <input
                        type="radio"
                        name="operatorSelection"
                        checked={selectedOperatorId === 'AUTO'}
                        onChange={() => setSelectedOperatorId('AUTO')}
                        className="hidden"
                      />
                      <HardHat className="w-4 h-4 opacity-70" />
                      <span className="font-semibold">Auto-Assign Available Operator</span>
                    </div>
                    <span className={`text-[10px] font-mono px-2 py-0.5 rounded ${
                      selectedOperatorId === 'AUTO' ? 'bg-zinc-800 text-zinc-200' : 'bg-zinc-100 text-zinc-600'
                    }`}>
                      POOLED
                    </span>
                  </label>

                  {allOperators.map((u) => {
                    const uId = u.id || u._id;
                    const isSelected = selectedOperatorId === uId;
                    const isAvailable = u.availabilityStatus === 'AVAILABLE';
                    return (
                      <label 
                        key={uId}
                        className={`flex items-center justify-between p-2.5 rounded-lg border cursor-pointer transition-colors ${
                          isSelected ? 'bg-zinc-900 text-white border-zinc-900' : 'bg-white border-zinc-200 text-zinc-700 hover:bg-zinc-50'
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <input
                            type="radio"
                            name="operatorSelection"
                            checked={isSelected}
                            onChange={() => setSelectedOperatorId(uId)}
                            className="hidden"
                          />
                          <span className="font-semibold">{u.name}</span>
                          <span className="font-mono text-[10px] opacity-75">({u.employeeId})</span>
                        </div>
                        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                          isAvailable ? 'bg-emerald-100 text-emerald-800' : 'bg-zinc-200 text-zinc-700'
                        }`}>
                          {u.availabilityStatus || 'OFFLINE'}
                        </span>
                      </label>
                    );
                  })}
                </div>
              </div>

            </div>

            {/* Footer */}
            <div className="px-6 py-4 border-t border-zinc-100 bg-zinc-50/50 flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setResumeModalOp(null)}
                className="px-4 py-2 bg-white hover:bg-zinc-100 text-zinc-700 border border-zinc-200 font-medium text-xs rounded-lg transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmResume}
                disabled={resuming}
                className="px-5 py-2 bg-emerald-600 hover:bg-emerald-700 active:scale-98 text-white font-semibold text-xs rounded-lg shadow-xs flex items-center gap-1.5 transition-all cursor-pointer"
              >
                {resuming ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Resuming Node...</span>
                  </>
                ) : (
                  <>
                    <Play className="w-3.5 h-3.5 fill-current" />
                    <span>Resume Operation</span>
                  </>
                )}
              </button>
            </div>

          </div>
        </div>
      )}

    </div>
  );
}
