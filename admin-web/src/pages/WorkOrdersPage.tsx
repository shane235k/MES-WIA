import { useState, useEffect } from 'react';
import { 
  Plus, X, Eye, Play, Trash2, 
  ArrowRight, ArrowLeft, HardHat, Cpu, Box, Layers, DollarSign, Calculator, Sparkles
} from 'lucide-react';
import { extractErrorMessage } from '../utils/apiError';
import AIWorkOrderModal from '../components/AIWorkOrderModal';

interface Product {
  id?: string;
  _id?: string;
  productCode: string;
  name: string;
  active?: boolean;
}

interface Workflow {
  id?: string;
  _id?: string;
  workflowCode: string;
  name: string;
  productId: string;
  version: number;
  operations: Array<{
    operationId: string;
    name: string;
    sequence: number;
    requiredMachineType: string;
    dependencies: string[];
    requiredMaterials?: Array<{
      materialId: string;
      specificationId?: string;
      quantity: number;
      unit?: string;
    }>;
  }>;
}

interface Material {
  id?: string;
  _id?: string;
  materialCode: string;
  name: string;
  unit: string;
  unitCost?: number;
  category?: string;
}

interface Supervisor {
  id?: string;
  _id?: string;
  name: string;
  employeeId: string;
}

interface Machine {
  id?: string;
  _id?: string;
  machineCode: string;
  name: string;
  type: string;
  status: string;
  supportedTypes?: string[];
}

interface Operator {
  id?: string;
  _id?: string;
  name: string;
  employeeId: string;
  status: string;
  skills?: string[];
}

interface WorkOrderOperation {
  operationId: string;
  name: string;
  sequence: number;
  assignedMachineId?: string;
  assignedOperatorId?: string;
  status: string;
  waitingReason?: string;
  dependencies: string[];
  requiredMaterials?: Array<{
    materialId: string;
    specificationId?: string;
    materialName?: string;
    specificationName?: string;
    unit?: string;
    quantityPerUnit: number;
    totalRequiredQuantity: number;
    quantityReserved: number;
    quantityConsumed: number;
    unitCost?: number;
    estimatedCost?: number;
    actualCost?: number;
  }>;
}

interface WorkOrder {
  id?: string;
  _id?: string;
  workOrderCode: string;
  name?: string;
  productId: string;
  workflowId: string;
  workflowVersion: number;
  supervisorId?: string;
  quantity: number;
  priority: string;
  status: string;
  dueDate: string;
  startedAt?: string | null;
  completedAt?: string | null;
  operations: WorkOrderOperation[];
  createdAt: string;
}

interface MaterialSummaryItem {
  materialId: string;
  materialCode?: string;
  materialName: string;
  specificationId?: string;
  specificationName?: string;
  unit: string;
  unitCost?: number;
  requiredQuantity: number;
  reservedQuantity: number;
  consumedQuantity: number;
  remainingQuantity: number;
  estimatedCost?: number;
  actualCost?: number;
  reservations?: Array<{
    reservationId?: string;
    lotId: string;
    lotNumber: string;
    operationId: string;
    quantityReserved: number;
    quantityConsumed: number;
    unitCost?: number;
    status: string;
  }>;
  operationBreakdown?: Array<{
    operationId: string;
    operationName?: string;
    quantityPerUnit: number;
    workOrderQuantity: number;
    requiredQuantity: number;
    quantityReserved: number;
    quantityConsumed: number;
    unit?: string;
  }>;
}

interface WorkOrderMaterialSummary {
  workOrderId: string;
  workOrderCode: string;
  status: string;
  materialStatus: string;
  totalEstimatedCost?: number;
  totalActualCost?: number;
  materials: MaterialSummaryItem[];
}

interface Props {
  onOpenDesigner?: (workflowId: string, workOrderId?: string) => void;
}

export default function WorkOrdersPage({ onOpenDesigner }: Props) {
  const [workOrders, setWorkOrders] = useState<WorkOrder[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [materials, setMaterials] = useState<Material[]>([]);
  const [supervisors, setSupervisors] = useState<Supervisor[]>([]);
  const [machines, setMachines] = useState<Machine[]>([]);
  const [operators, setOperators] = useState<Operator[]>([]);
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isAiModalOpen, setIsAiModalOpen] = useState(false);

  // Materials Detail Modal state
  const [selectedWoForMaterials, setSelectedWoForMaterials] = useState<WorkOrder | null>(null);
  const [materialSummary, setMaterialSummary] = useState<WorkOrderMaterialSummary | null>(null);
  const [loadingMaterials, setLoadingMaterials] = useState(false);

  // Multi-Step Modal Phase (1: Details, 2: Personnel & Machines, 3: Review)
  const [modalPhase, setModalPhase] = useState<1 | 2 | 3>(1);

  // Form states
  const [workOrderCode, setWorkOrderCode] = useState('');
  const [workOrderName, setWorkOrderName] = useState('');
  const [productId, setProductId] = useState('');
  const [workflowId, setWorkflowId] = useState('');
  const [supervisorId, setSupervisorId] = useState('');
  const [quantity, setQuantity] = useState<number>(10);
  const [priority, setPriority] = useState('HIGH');
  const [dueDate, setDueDate] = useState('');

  const handleApplyDraftToWizard = (draft: any) => {
    if (!draft) return;
    setProductId(draft.productId || '');
    setWorkflowId(draft.workflowId || '');
    setQuantity(Number(draft.quantity) || 10);
    setWorkOrderCode(draft.workOrderCode || `WO-${draft.productCode || 'PROD'}-${Date.now().toString().slice(-4)}`);
    setWorkOrderName(draft.name || `${draft.productCode || 'Batch'} Production Run`);
    setPriority(draft.priority || 'NORMAL');
    setSupervisorId(draft.supervisorId || '');
    if (draft.dueDate) {
      setDueDate(typeof draft.dueDate === 'string' ? draft.dueDate.split('T')[0] : new Date(draft.dueDate).toISOString().split('T')[0]);
    }

    // Pre-populate operations if present
    if (draft.operations && draft.operations.length > 0) {
      setStepAssignments(draft.operations.map((op: any) => ({
        operationId: op.operationId,
        name: op.name || '',
        sequence: op.sequence || 1,
        requiredMachineType: op.requiredMachineType || 'GENERIC',
        assignedMachineId: op.assignedMachineId || '',
        assignedOperatorId: op.assignedOperatorId || '',
        requiredMaterials: op.requiredMaterials || []
      })));
    }

    setModalPhase(1);
    setIsModalOpen(true);
  };

  // Per-operation assignment state during creation
  const [stepAssignments, setStepAssignments] = useState<Array<{
    operationId: string;
    name: string;
    sequence: number;
    requiredMachineType: string;
    assignedMachineId: string;
    assignedOperatorId: string;
    requiredMaterials?: any[];
  }>>([]);

  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  const fetchData = async () => {
    try {
      const [woRes, prodRes, wfRes, matRes, supRes, machRes, operRes] = await Promise.all([
        fetch(`${API_URL}/api/work-orders`),
        fetch(`${API_URL}/api/products`),
        fetch(`${API_URL}/api/workflows`),
        fetch(`${API_URL}/api/materials`),
        fetch(`${API_URL}/api/users/supervisors`),
        fetch(`${API_URL}/api/machines`),
        fetch(`${API_URL}/api/users/operators`)
      ]);
      
      if (woRes.ok) {
        const d = await woRes.json();
        setWorkOrders(Array.isArray(d) ? d : []);
      }
      if (prodRes.ok) {
        const d = await prodRes.json();
        setProducts(Array.isArray(d) ? d : []);
      }
      if (wfRes.ok) {
        const d = await wfRes.json();
        setWorkflows(Array.isArray(d) ? d : []);
      }
      if (matRes.ok) {
        const d = await matRes.json();
        setMaterials(Array.isArray(d) ? d : []);
      }
      if (supRes.ok) {
        const d = await supRes.json();
        setSupervisors(Array.isArray(d) ? d : []);
      }
      if (machRes.ok) {
        const d = await machRes.json();
        setMachines(Array.isArray(d) ? d : []);
      }
      if (operRes.ok) {
        const d = await operRes.json();
        setOperators(Array.isArray(d) ? d : []);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to fetch data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();

    // WebSocket for real-time live execution and material updates
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = API_URL.replace(/^https?:\/\//, '');
    const wsUrl = `${protocol}//${wsHost}/ws`;
    
    let ws: WebSocket | null = null;
    try {
      ws = new WebSocket(wsUrl);
      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (
            msg.type === 'WORK_ORDER_UPDATED' ||
            msg.type === 'OPERATION_PROGRESS' ||
            msg.type === 'OPERATION_COMPLETED' ||
            msg.type === 'MATERIAL_RESERVED' ||
            msg.type === 'MATERIAL_CONSUMED' ||
            msg.type === 'WORK_ORDER_MATERIAL_SHORTAGE'
          ) {
            fetchData();
            // If the materials modal is currently open for this work order, refresh its summary
            if (selectedWoForMaterials) {
              const woId = selectedWoForMaterials.id || selectedWoForMaterials._id;
              if (msg.data?.workOrderId === woId) {
                fetchMaterialSummary(woId!);
              }
            }
          }
        } catch (e) {
          console.error('Error parsing WS message in WorkOrdersPage', e);
        }
      };
    } catch (e) {
      console.warn('WebSocket connection error:', e);
    }

    return () => {
      if (ws) ws.close();
    };
  }, [selectedWoForMaterials]);

  const fetchMaterialSummary = async (woId: string) => {
    setLoadingMaterials(true);
    try {
      const res = await fetch(`${API_URL}/api/work-orders/${woId}/materials`);
      if (res.ok) {
        setMaterialSummary(await res.json());
      }
    } catch (err) {
      console.error('Failed to fetch material summary:', err);
    } finally {
      setLoadingMaterials(false);
    }
  };

  const handleOpenMaterialsModal = (wo: WorkOrder) => {
    setSelectedWoForMaterials(wo);
    const woId = wo.id || wo._id || '';
    fetchMaterialSummary(woId);
  };

  const handleOpenCreateModal = () => {
    setError(null);
    setModalPhase(1);
    setWorkOrderCode(`WO-${Date.now().toString().slice(-6)}`);
    setWorkOrderName('');
    const firstP = products[0]?.id || products[0]?._id || '';
    setProductId(firstP);
    
    const availableWfs = workflows.filter(w => w.productId === firstP);
    setWorkflowId(availableWfs[0]?.id || availableWfs[0]?._id || '');
    setSupervisorId(supervisors[0]?.id || supervisors[0]?._id || '');
    setQuantity(20);
    setPriority('HIGH');
    
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 2);
    setDueDate(tomorrow.toISOString().split('T')[0]);
    
    setIsModalOpen(true);
  };

  const handleProductChange = (prodId: string) => {
    setProductId(prodId);
    const matchingWfs = workflows.filter(w => w.productId === prodId);
    if (matchingWfs.length > 0) {
      setWorkflowId(matchingWfs[0].id || matchingWfs[0]._id || '');
    } else {
      setWorkflowId('');
    }
  };

  // Instant Cost Calculation Helper for the current form state
  const calculateInstantCost = () => {
    const currentWf = workflows.find(w => (w.id || w._id) === workflowId);
    if (!currentWf || !currentWf.operations) return { totalEstimatedCost: 0, costPerUnit: 0, items: [] };

    const batchQty = Number(quantity) || 0;
    let totalEstimatedCost = 0;
    const itemsMap: Record<string, {
      materialId: string;
      materialCode: string;
      materialName: string;
      unit: string;
      qtyPerUnit: number;
      totalQty: number;
      unitCost: number;
      subtotal: number;
    }> = {};

    for (const op of currentWf.operations) {
      for (const rm of op.requiredMaterials || []) {
        const mId = rm.materialId;
        const mat = materials.find(m => (m.id || m._id) === mId);
        const uCost = mat?.unitCost ?? 0;
        const qPerUnit = Number(rm.quantity || 0);

        if (!itemsMap[mId]) {
          itemsMap[mId] = {
            materialId: mId,
            materialCode: mat?.materialCode || 'RAW',
            materialName: mat?.name || 'Raw Material',
            unit: rm.unit || mat?.unit || 'units',
            qtyPerUnit: 0,
            totalQty: 0,
            unitCost: uCost,
            subtotal: 0
          };
        }
        itemsMap[mId].qtyPerUnit += qPerUnit;
      }
    }

    const items = Object.values(itemsMap).map(item => {
      const totalQty = Math.round(item.qtyPerUnit * batchQty * 10000) / 10000;
      const subtotal = Math.round(totalQty * item.unitCost * 100) / 100;
      totalEstimatedCost += subtotal;
      return {
        ...item,
        totalQty,
        subtotal
      };
    });

    const costPerUnit = batchQty > 0 ? Math.round((totalEstimatedCost / batchQty) * 100) / 100 : 0;
    return {
      totalEstimatedCost: Math.round(totalEstimatedCost * 100) / 100,
      costPerUnit,
      items
    };
  };

  // Get total estimated cost for a work order from its operations snapshot
  const getWorkOrderCost = (wo: WorkOrder) => {
    let total = 0;
    for (const op of wo.operations || []) {
      for (const rm of op.requiredMaterials || []) {
        if (rm.estimatedCost) {
          total += rm.estimatedCost;
        } else if (rm.unitCost && rm.totalRequiredQuantity) {
          total += rm.unitCost * rm.totalRequiredQuantity;
        }
      }
    }
    return total;
  };

  const handleNextStep1 = () => {
    if (!productId || !workflowId) {
      setError('Please select a valid Product and Workflow');
      return;
    }
    if (quantity <= 0) {
      setError('Output quantity must be greater than 0');
      return;
    }

    const selectedWf = workflows.find(w => (w.id || w._id) === workflowId);
    if (!selectedWf || !selectedWf.operations || selectedWf.operations.length === 0) {
      setError('Selected workflow has no defined operations');
      return;
    }

    const initialAssignments = selectedWf.operations.map(op => {
      const compatibleMachines = machines.filter(m => 
        m.type === op.requiredMachineType || m.supportedTypes?.includes(op.requiredMachineType)
      );
      const qualifiedOperators = operators.filter(o => 
        !o.skills || o.skills.length === 0 || o.skills.includes(op.requiredMachineType)
      );

      const chosenMachine = compatibleMachines.length > 0 ? (compatibleMachines[0].id || compatibleMachines[0]._id) : '';
      const chosenOperator = qualifiedOperators.length > 0 ? (qualifiedOperators[0].id || qualifiedOperators[0]._id) : '';

      return {
        operationId: op.operationId,
        name: op.name,
        sequence: op.sequence,
        requiredMachineType: op.requiredMachineType,
        assignedMachineId: chosenMachine || '',
        assignedOperatorId: chosenOperator || '',
        requiredMaterials: op.requiredMaterials || []
      };
    });

    setStepAssignments(initialAssignments);
    setError(null);
    setModalPhase(2);
  };

  const handleNextStep2 = () => {
    setError(null);
    setModalPhase(3);
  };

  const handleFinalSubmit = async () => {
    setError(null);
    setLoading(true);

    const selectedWf = workflows.find(w => (w.id || w._id) === workflowId);
    const payload = {
      workOrderCode,
      name: workOrderName.trim() || `${workOrderCode} Production Batch`,
      productId,
      workflowId,
      workflowVersion: selectedWf?.version || 1,
      supervisorId: supervisorId || null,
      quantity: Number(quantity),
      priority,
      dueDate: new Date(dueDate).toISOString(),
      operations: stepAssignments.map(s => ({
        operationId: s.operationId,
        assignedMachineId: s.assignedMachineId || null,
        assignedOperatorId: s.assignedOperatorId || null
      }))
    };

    try {
      const res = await fetch(`${API_URL}/api/work-orders`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(extractErrorMessage(errData, 'Failed to create work order'));
      }

      await fetchData();
      setIsModalOpen(false);
    } catch (err: any) {
      setError(err.message || 'An unexpected error occurred');
    } finally {
      setLoading(false);
    }
  };

  const handleStartProduction = async (wo: WorkOrder, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const woId = wo.id || wo._id;
      const res = await fetch(`${API_URL}/api/work-orders/${woId}/start`, {
        method: 'POST'
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(extractErrorMessage(errData, 'Failed to start work order'));
      }

      await fetchData();
    } catch (err: any) {
      setError(err.message || 'An unexpected error occurred');
    }
  };

  const handleDeleteWorkOrder = async (woId: string, woCode: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm(`Are you sure you want to cancel & delete Work Order ${woCode}? Reserved materials will be returned to inventory.`)) return;

    try {
      const res = await fetch(`${API_URL}/api/work-orders/${woId}`, {
        method: 'DELETE'
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(extractErrorMessage(errData, 'Failed to delete work order'));
      }

      await fetchData();
    } catch (err: any) {
      setError(err.message || 'An unexpected error occurred');
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'COMPLETED':
        return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">COMPLETED</span>;
      case 'IN_PROGRESS':
        return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-50 text-blue-700 border border-blue-200 animate-pulse">IN PROGRESS</span>;
      case 'WAITING_FOR_MATERIAL':
        return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-50 text-amber-700 border border-amber-200">WAITING MATERIAL</span>;
      case 'PAUSED':
        return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-50 text-amber-700 border border-amber-200">PAUSED</span>;
      case 'FAILED':
        return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-50 text-rose-700 border border-rose-200">FAILED</span>;
      default:
        return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-zinc-100 text-zinc-700 border border-zinc-200">PLANNED</span>;
    }
  };

  const instantCost = calculateInstantCost();

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-900 flex items-center gap-2">
            <Layers className="w-6 h-6 text-zinc-900" />
            Production Work Orders
          </h1>
          <p className="text-xs text-zinc-500 mt-1">
            Schedule execution batches, inspect instant building costs, allocate physical lots, and track real-time shop floor progress.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsAiModalOpen(true)}
            className="inline-flex items-center justify-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold text-zinc-900 bg-white hover:bg-zinc-50 rounded-lg transition-all shadow-2xs border border-zinc-300 cursor-pointer"
          >
            <Sparkles className="w-3.5 h-3.5 text-zinc-900" />
            <span>Create with AI</span>
          </button>
          <button
            onClick={handleOpenCreateModal}
            className="inline-flex items-center justify-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold text-white bg-zinc-900 rounded-lg hover:bg-zinc-800 transition-colors shadow-2xs cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            Schedule Work Order
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-700 flex items-center justify-between font-mono">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-rose-500 hover:text-rose-700 text-xs">✕</button>
        </div>
      )}

      {/* Grid of Work Orders */}
      {loading ? (
        <div className="flex items-center justify-center p-12 text-zinc-500 text-xs font-mono">
          Loading production work orders...
        </div>
      ) : workOrders.length === 0 ? (
        <div className="p-8 border border-dashed border-zinc-200 rounded-xl text-center text-zinc-500 text-xs">
          No work orders scheduled yet.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {workOrders.map((wo) => {
            const woId = wo.id || wo._id || '';
            const product = products.find(p => (p.id || p._id) === wo.productId);
            const totalOps = wo.operations?.length || 0;
            const completedOps = wo.operations?.filter(o => o.status === 'COMPLETED').length || 0;
            const estCost = getWorkOrderCost(wo);
            
            return (
              <div
                key={woId}
                className="bg-white border border-zinc-200 rounded-2xl p-5 shadow-2xs hover:shadow-md transition-all flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div>
                      <h3 className="font-bold text-zinc-900 text-base leading-tight">
                        {wo.name || wo.workOrderCode}
                      </h3>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        <span className="text-xs font-mono font-bold text-zinc-400 uppercase tracking-wider">
                          {wo.workOrderCode}
                        </span>
                        <span className="text-xs text-zinc-500 font-medium truncate max-w-[180px]">
                          • {product ? product.name : wo.productId}
                        </span>
                      </div>
                    </div>
                    {getStatusBadge(wo.status)}
                  </div>

                  <div className="space-y-1.5 text-xs text-zinc-600 my-3 border-t border-b border-zinc-100 py-3">
                    <div className="flex justify-between">
                      <span className="text-zinc-400">Target Output:</span>
                      <span className="font-mono font-bold text-zinc-800">{wo.quantity} units</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-zinc-400">Estimated Material Cost:</span>
                      <span className="font-mono font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                        ₹{estCost.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-400">Priority:</span>
                      <span className="font-semibold text-zinc-800">{wo.priority}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-400">Due Date:</span>
                      <span className="font-mono">{new Date(wo.dueDate).toLocaleDateString()}</span>
                    </div>
                    <div className="flex justify-between items-center pt-1">
                      <span className="text-zinc-400">Operations Progress:</span>
                      <span className="font-mono font-bold text-zinc-900">{completedOps}/{totalOps} steps</span>
                    </div>
                  </div>

                  {/* Operation Step Pills */}
                  <div className="flex flex-wrap gap-1 mb-3">
                    {wo.operations.map((op) => (
                      <span
                        key={op.operationId}
                        className={`px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold border ${
                          op.status === 'COMPLETED' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
                          op.status === 'INTERRUPTED' ? 'bg-rose-50 text-rose-700 border-rose-200 font-bold animate-pulse' :
                          op.status === 'IN_PROGRESS' ? 'bg-blue-50 text-blue-700 border-blue-200 animate-pulse' :
                          op.status === 'WAITING_FOR_RESOURCE' ? 'bg-amber-50 text-amber-700 border-amber-200' :
                          'bg-zinc-100 text-zinc-500 border-zinc-200'
                        }`}
                        title={`${op.operationId}: ${op.status} ${op.waitingReason ? `(${op.waitingReason})` : ''}`}
                      >
                        {op.operationId}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="flex items-center justify-between gap-2 mt-2 pt-3 border-t border-zinc-100">
                  <div className="flex items-center gap-1.5">
                    {wo.status === 'PLANNED' ? (
                      <button
                        onClick={(e) => handleStartProduction(wo, e)}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold shadow-xs transition-colors cursor-pointer"
                      >
                        <Play className="w-3.5 h-3.5 fill-current" />
                        Start
                      </button>
                    ) : (
                      <button
                        onClick={() => onOpenDesigner && onOpenDesigner(wo.workflowId, woId)}
                        className="inline-flex items-center gap-1 text-xs font-semibold text-zinc-900 hover:text-zinc-600 bg-zinc-100 hover:bg-zinc-200 px-3 py-1.5 rounded-lg transition-colors cursor-pointer"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        Execution
                      </button>
                    )}

                    <button
                      onClick={() => handleOpenMaterialsModal(wo)}
                      className="inline-flex items-center gap-1 text-xs font-semibold text-zinc-700 hover:text-zinc-900 bg-white border border-zinc-200 hover:bg-zinc-50 px-2.5 py-1.5 rounded-lg transition-colors cursor-pointer"
                      title="Inspect Required Materials & Costing"
                    >
                      <Box className="w-3.5 h-3.5 text-zinc-500" />
                      BOM & Cost
                    </button>
                  </div>

                  <button
                    onClick={(e) => handleDeleteWorkOrder(woId, wo.workOrderCode, e)}
                    className="p-1.5 text-zinc-400 hover:text-rose-600 hover:bg-rose-50 rounded-md transition-colors cursor-pointer"
                    title="Delete Work Order"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Materials & Costing Detail Drawer/Modal */}
      {selectedWoForMaterials && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[92vh] overflow-hidden border border-zinc-200 flex flex-col">
            {/* Modal Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200 bg-zinc-50/50">
              <div className="flex items-center gap-3">
                <Box className="w-5 h-5 text-zinc-900" />
                <div>
                  <h2 className="text-base font-bold text-zinc-900 flex items-center gap-2">
                    Materials, Lots & Costing: {selectedWoForMaterials.workOrderCode}
                  </h2>
                  <p className="text-xs text-zinc-500">
                    Live snapshot of bill of materials, lot reservations, and actual consumption.
                  </p>
                </div>
              </div>
              <button
                onClick={() => setSelectedWoForMaterials(null)}
                className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-600 hover:bg-zinc-100 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Modal Content */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {loadingMaterials ? (
                <div className="flex items-center justify-center py-12 text-zinc-500 text-xs font-mono">
                  Loading material allocations and live costing...
                </div>
              ) : materialSummary ? (
                <>
                  {/* Top Stats Cards: Production Target, Material Status & Costing */}
                  <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
                    <div className="p-4 bg-indigo-50/70 border border-indigo-200 rounded-xl space-y-1">
                      <span className="text-xs text-indigo-700 font-semibold">Production Target</span>
                      <div className="text-lg font-bold font-mono text-indigo-950">
                        {selectedWoForMaterials.quantity} finished units
                      </div>
                      <span className="text-[10px] text-indigo-600 font-mono block">
                        Status: {selectedWoForMaterials.status}
                      </span>
                    </div>

                    <div className="p-4 bg-zinc-50 border border-zinc-200 rounded-xl space-y-1">
                      <span className="text-xs text-zinc-500 font-medium">Material Status</span>
                      <div className="flex items-center gap-2">
                        <span className={`px-2.5 py-1 rounded-md text-xs font-mono font-bold ${
                          materialSummary.materialStatus === 'READY' ? 'bg-emerald-100 text-emerald-800' :
                          materialSummary.materialStatus === 'RESERVED' ? 'bg-blue-100 text-blue-800' :
                          materialSummary.materialStatus === 'CONSUMING' ? 'bg-indigo-100 text-indigo-800' :
                          materialSummary.materialStatus === 'COMPLETED' ? 'bg-zinc-200 text-zinc-800' :
                          'bg-amber-100 text-amber-800'
                        }`}>
                          {materialSummary.materialStatus}
                        </span>
                      </div>
                    </div>

                    <div className="p-4 bg-zinc-50 border border-zinc-200 rounded-xl space-y-1">
                      <span className="text-xs text-zinc-500 font-medium">Estimated Material Cost</span>
                      <div className="text-lg font-bold font-mono text-zinc-900">
                        ₹{(materialSummary.totalEstimatedCost || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </div>
                    </div>

                    <div className="p-4 bg-emerald-50/60 border border-emerald-200 rounded-xl space-y-1">
                      <span className="text-xs text-emerald-700 font-medium">Actual Consumed Cost</span>
                      <div className="text-lg font-bold font-mono text-emerald-900">
                        ₹{(materialSummary.totalActualCost || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </div>
                    </div>
                  </div>

                  {/* Detailed Requirements Table */}
                  <div className="bg-white border border-zinc-200 rounded-xl overflow-hidden shadow-2xs space-y-2">
                    <div className="px-4 py-3 bg-zinc-50/70 border-b border-zinc-100 font-bold text-xs text-zinc-800 flex justify-between items-center">
                      <span>Required Materials Snapshot & Operation Breakdown</span>
                      <span className="text-[10px] text-zinc-400 font-normal">Material input does not multiply product output</span>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs border-collapse font-mono">
                        <thead>
                          <tr className="border-b border-zinc-100 bg-zinc-50/40 text-zinc-500 text-[11px]">
                            <th className="py-2.5 px-4 font-semibold">Material / Spec</th>
                            <th className="py-2.5 px-4 font-semibold text-right">Req. Qty</th>
                            <th className="py-2.5 px-4 font-semibold text-right">Reserved</th>
                            <th className="py-2.5 px-4 font-semibold text-right">Consumed</th>
                            <th className="py-2.5 px-4 font-semibold text-right">Remaining</th>
                            <th className="py-2.5 px-4 font-semibold text-right">Est. Cost (₹)</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-zinc-100">
                          {materialSummary.materials.map((m) => (
                            <tr key={m.materialId} className="hover:bg-zinc-50/50">
                              <td className="py-3 px-4">
                                <div className="font-bold text-zinc-900 font-sans">{m.materialName}</div>
                                {m.specificationName && (
                                  <div className="text-[10px] text-zinc-400">{m.specificationName}</div>
                                )}
                                {/* Operation breakdown tags */}
                                {m.operationBreakdown && m.operationBreakdown.length > 0 && (
                                  <div className="flex flex-wrap gap-1 mt-1.5 font-mono text-[10px]">
                                    {m.operationBreakdown.map((opB: any, opBIdx: number) => (
                                      <span key={opBIdx} className="bg-zinc-100 border border-zinc-200 px-1.5 py-0.5 rounded text-zinc-700">
                                        {opB.operationId}: {opB.quantityPerUnit} {opB.unit}/u × {opB.workOrderQuantity} = <strong>{opB.requiredQuantity} {opB.unit}</strong>
                                      </span>
                                    ))}
                                  </div>
                                )}
                              </td>
                              <td className="py-3 px-4 text-right font-bold text-zinc-900">
                                {m.requiredQuantity} {m.unit}
                              </td>
                              <td className="py-3 px-4 text-right text-blue-700 font-semibold">
                                {m.reservedQuantity} {m.unit}
                              </td>
                              <td className="py-3 px-4 text-right text-emerald-700 font-bold">
                                {m.consumedQuantity} {m.unit}
                              </td>
                              <td className="py-3 px-4 text-right text-zinc-600">
                                {m.remainingQuantity} {m.unit}
                              </td>
                              <td className="py-3 px-4 text-right font-bold text-zinc-900">
                                ₹{(m.estimatedCost || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Active Reservations by Physical Lot */}
                  <div className="space-y-2">
                    <div className="text-xs font-bold text-zinc-800">
                      Allocated Physical Lots (FIFO / FEFO)
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {materialSummary.materials.flatMap(m => m.reservations || []).length === 0 ? (
                        <div className="p-4 bg-zinc-50 border border-dashed border-zinc-200 rounded-xl text-xs text-zinc-400 col-span-2 text-center">
                          No physical inventory lots reserved yet.
                        </div>
                      ) : (
                        materialSummary.materials.flatMap(m => m.reservations || []).map((r, i) => (
                          <div key={i} className="p-3 bg-zinc-50 border border-zinc-200 rounded-xl space-y-1 font-mono text-xs flex justify-between items-center">
                            <div>
                              <div className="font-bold text-zinc-900 flex items-center gap-1.5">
                                <Box className="w-3.5 h-3.5 text-zinc-600" />
                                {r.lotNumber}
                              </div>
                              <div className="text-[11px] text-zinc-500">Operation: {r.operationId}</div>
                            </div>
                            <div className="text-right">
                              <span className="font-bold text-blue-700 block">{r.quantityReserved} reserved</span>
                              {r.unitCost && (
                                <span className="text-[10px] text-zinc-400">@ ₹{r.unitCost}/unit</span>
                              )}
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </>
              ) : (
                <div className="text-center py-8 text-xs text-zinc-400">
                  No material requirements defined for this work order.
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-4 bg-zinc-50 border-t border-zinc-200 flex justify-end">
              <button
                onClick={() => setSelectedWoForMaterials(null)}
                className="px-4 py-1.5 text-xs font-semibold text-zinc-700 bg-white border border-zinc-300 rounded-lg hover:bg-zinc-50 cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Creation Modal (3-Step Wizard) */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl overflow-hidden border border-zinc-200 flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200 bg-zinc-50/50">
              <div>
                <h2 className="text-base font-bold text-zinc-900">
                  Schedule New Production Work Order
                </h2>
                <div className="flex items-center gap-2 mt-1">
                  <span className={`text-xs font-medium ${modalPhase === 1 ? 'text-zinc-900 font-bold' : 'text-zinc-400'}`}>
                    1. Batch Details & Costing
                  </span>
                  <span className="text-xs text-zinc-300">→</span>
                  <span className={`text-xs font-medium ${modalPhase === 2 ? 'text-zinc-900 font-bold' : 'text-zinc-400'}`}>
                    2. Machine & Worker Routing
                  </span>
                  <span className="text-xs text-zinc-300">→</span>
                  <span className={`text-xs font-medium ${modalPhase === 3 ? 'text-zinc-900 font-bold' : 'text-zinc-400'}`}>
                    3. Review & Launch
                  </span>
                </div>
              </div>
              <button
                onClick={() => setIsModalOpen(false)}
                className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-600 hover:bg-zinc-100 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Body */}
            <div className="p-6 space-y-4 max-h-[75vh] overflow-y-auto">
              {error && (
                <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-700">
                  {error}
                </div>
              )}

              {/* PHASE 1: Basic Info & Live Costing */}
              {modalPhase === 1 && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-semibold text-zinc-700 mb-1">Work Order Code</label>
                      <input
                        type="text"
                        required
                        value={workOrderCode}
                        onChange={(e) => setWorkOrderCode(e.target.value.toUpperCase())}
                        className="w-full px-3 py-2 border border-zinc-300 rounded-lg text-xs font-mono uppercase font-bold"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-zinc-700 mb-1">Batch Name / Reference</label>
                      <input
                        type="text"
                        value={workOrderName}
                        onChange={(e) => setWorkOrderName(e.target.value)}
                        placeholder="e.g. Batch #4412"
                        className="w-full px-3 py-2 border border-zinc-300 rounded-lg text-xs font-medium"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-semibold text-zinc-700 mb-1">Target Product</label>
                      <select
                        value={productId}
                        onChange={(e) => handleProductChange(e.target.value)}
                        className="w-full px-3 py-2 border border-zinc-300 rounded-lg text-xs font-medium bg-white"
                      >
                        {products.map(p => (
                          <option key={p.id || p._id} value={p.id || p._id}>
                            {p.productCode} — {p.name}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-zinc-700 mb-1">Canonical Routing Workflow</label>
                      <select
                        value={workflowId}
                        onChange={(e) => setWorkflowId(e.target.value)}
                        className="w-full px-3 py-2 border border-zinc-300 rounded-lg text-xs font-medium bg-white font-mono"
                      >
                        {workflows.filter(w => w.productId === productId).map(w => (
                          <option key={w.id || w._id} value={w.id || w._id}>
                            {w.workflowCode} — {w.name} (v{w.version})
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <label className="block text-xs font-semibold text-zinc-700 mb-1">Output Quantity (Units)</label>
                      <input
                        type="number"
                        min="1"
                        required
                        value={quantity}
                        onChange={(e) => setQuantity(Number(e.target.value))}
                        className="w-full px-3 py-2 border border-zinc-300 rounded-lg text-xs font-mono font-bold text-zinc-900"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-zinc-700 mb-1">Priority</label>
                      <select
                        value={priority}
                        onChange={(e) => setPriority(e.target.value)}
                        className="w-full px-3 py-2 border border-zinc-300 rounded-lg text-xs font-semibold"
                      >
                        <option value="LOW">LOW</option>
                        <option value="NORMAL">NORMAL</option>
                        <option value="HIGH">HIGH</option>
                        <option value="CRITICAL">CRITICAL</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-zinc-700 mb-1">Due Date</label>
                      <input
                        type="date"
                        required
                        value={dueDate}
                        onChange={(e) => setDueDate(e.target.value)}
                        className="w-full px-3 py-2 border border-zinc-300 rounded-lg text-xs font-mono"
                      />
                    </div>
                  </div>

                  {/* INSTANT COST OF BUILDING PREVIEW */}
                  <div className="bg-zinc-900 text-white rounded-xl p-4 space-y-3 shadow-sm">
                    <div className="flex items-center justify-between border-b border-zinc-800 pb-2.5">
                      <div className="flex items-center gap-2">
                        <Calculator className="w-4 h-4 text-emerald-400" />
                        <span className="font-bold text-xs uppercase tracking-wider text-zinc-200">
                          Instant Cost of Building Preview
                        </span>
                      </div>
                      <span className="text-[11px] font-mono text-zinc-400">
                        {quantity} Finished Unit(s)
                      </span>
                    </div>

                    <div className="grid grid-cols-2 gap-3 font-mono">
                      <div className="bg-zinc-800/80 p-2.5 rounded-lg border border-zinc-700/60">
                        <span className="text-[10px] text-zinc-400 block uppercase">Total Batch Material Cost</span>
                        <span className="text-lg font-bold text-emerald-400">
                          ₹{instantCost.totalEstimatedCost.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                        </span>
                      </div>
                      <div className="bg-zinc-800/80 p-2.5 rounded-lg border border-zinc-700/60">
                        <span className="text-[10px] text-zinc-400 block uppercase">Material Cost / Unit</span>
                        <span className="text-lg font-bold text-zinc-200">
                          ₹{instantCost.costPerUnit.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                        </span>
                      </div>
                    </div>

                    {instantCost.items.length > 0 && (
                      <div className="space-y-1.5 text-xs font-mono pt-1">
                        <span className="text-[10px] text-zinc-400 block uppercase font-sans">Scaled Raw Material Consumption:</span>
                        <div className="space-y-1 max-h-28 overflow-y-auto pr-1">
                          {instantCost.items.map((item, i) => (
                            <div key={i} className="flex justify-between items-center bg-zinc-800/50 px-2.5 py-1 rounded text-[11px]">
                              <span className="text-zinc-300">
                                {item.materialName}: <strong>{item.totalQty} {item.unit}</strong> (@ ₹{item.unitCost})
                              </span>
                              <span className="text-emerald-400 font-bold">
                                ₹{item.subtotal.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-zinc-700 mb-1">Shift Supervisor</label>
                    <select
                      value={supervisorId}
                      onChange={(e) => setSupervisorId(e.target.value)}
                      className="w-full px-3 py-2 border border-zinc-300 rounded-lg text-xs font-medium bg-white"
                    >
                      {supervisors.map(s => (
                        <option key={s.id || s._id} value={s.id || s._id}>
                          {s.name} ({s.employeeId})
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              )}

              {/* PHASE 2: Personnel & Machines */}
              {modalPhase === 2 && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between pb-2 border-b border-zinc-100">
                    <span className="text-xs font-bold text-zinc-900 uppercase tracking-wider">
                      Workstation & Operator Assignments
                    </span>
                    <span className="text-xs font-mono text-emerald-700 font-bold bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                      Total Cost: ₹{instantCost.totalEstimatedCost.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </span>
                  </div>

                  <div className="space-y-3 max-h-80 overflow-y-auto pr-1">
                    {stepAssignments.map((step, idx) => {
                      const compatibleMachines = machines.filter(m => 
                        m.type === step.requiredMachineType || m.supportedTypes?.includes(step.requiredMachineType)
                      );
                      const qualifiedOperators = operators.filter(o => 
                        !o.skills || o.skills.length === 0 || o.skills.includes(step.requiredMachineType)
                      );

                      return (
                        <div key={step.operationId} className="p-3.5 bg-zinc-50 rounded-xl border border-zinc-200 space-y-2.5">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-xs font-bold bg-white px-2 py-0.5 rounded border text-zinc-800">
                                {step.operationId}
                              </span>
                              <span className="text-xs font-bold text-zinc-900">{step.name}</span>
                            </div>
                            <span className="px-2 py-0.5 bg-zinc-200/70 border border-zinc-300 rounded text-[10px] font-mono uppercase font-bold text-zinc-700">
                              {step.requiredMachineType}
                            </span>
                          </div>

                          <div className="grid grid-cols-2 gap-2 text-xs">
                            <div>
                              <label className="block text-[11px] font-semibold text-zinc-600 mb-1 flex items-center gap-1">
                                <Cpu className="w-3 h-3 text-zinc-500" />
                                Assigned Machine
                              </label>
                              <select
                                value={step.assignedMachineId}
                                onChange={(e) => {
                                  const updated = [...stepAssignments];
                                  updated[idx].assignedMachineId = e.target.value;
                                  setStepAssignments(updated);
                                }}
                                className="w-full px-2.5 py-1.5 bg-white border border-zinc-300 rounded-lg text-xs"
                              >
                                <option value="">Select Machine...</option>
                                {compatibleMachines.map(m => (
                                  <option key={m.id || m._id} value={m.id || m._id}>
                                    {m.machineCode} — {m.name} ({m.status})
                                  </option>
                                ))}
                              </select>
                            </div>

                            <div>
                              <label className="block text-[11px] font-semibold text-zinc-600 mb-1 flex items-center gap-1">
                                <HardHat className="w-3 h-3 text-amber-600" />
                                Assigned Operator
                              </label>
                              <select
                                value={step.assignedOperatorId}
                                onChange={(e) => {
                                  const updated = [...stepAssignments];
                                  updated[idx].assignedOperatorId = e.target.value;
                                  setStepAssignments(updated);
                                }}
                                className="w-full px-2.5 py-1.5 bg-white border border-zinc-300 rounded-lg text-xs"
                              >
                                <option value="">Select Operator...</option>
                                {qualifiedOperators.map(o => (
                                  <option key={o.id || o._id} value={o.id || o._id}>
                                    {o.name} ({o.employeeId})
                                  </option>
                                ))}
                              </select>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* PHASE 3: Review & Instant Cost of Building Breakdown */}
              {modalPhase === 3 && (
                <div className="space-y-4">
                  <div className="bg-zinc-50 p-4 rounded-xl border border-zinc-200 space-y-2 text-xs">
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <span className="text-zinc-400 text-[10px] block">Work Order Code:</span>
                        <strong className="font-mono text-zinc-900 font-bold">{workOrderCode}</strong>
                      </div>
                      <div>
                        <span className="text-zinc-400 text-[10px] block">Target Quantity:</span>
                        <strong className="text-zinc-900">{quantity} units</strong>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-2 pt-2 border-t border-zinc-200/60">
                      <div>
                        <span className="text-zinc-400 text-[10px] block">Product:</span>
                        <strong className="text-zinc-900">{products.find(p => (p.id || p._id) === productId)?.name}</strong>
                      </div>
                      <div>
                        <span className="text-zinc-400 text-[10px] block">Shift Supervisor:</span>
                        <strong className="text-zinc-900">{supervisors.find(s => (s.id || s._id) === supervisorId)?.name || 'Unassigned'}</strong>
                      </div>
                    </div>
                  </div>

                  {/* Prominent Instant Cost Summary Box */}
                  <div className="bg-emerald-950 text-white rounded-xl p-4 space-y-3 shadow-md border border-emerald-800">
                    <div className="flex items-center justify-between border-b border-emerald-800/80 pb-2">
                      <div className="flex items-center gap-2">
                        <DollarSign className="w-5 h-5 text-emerald-400" />
                        <span className="font-bold text-xs uppercase tracking-wider text-emerald-200">
                          Total Instant Building Cost (BOM)
                        </span>
                      </div>
                      <span className="text-xs font-mono font-bold text-emerald-300">
                        ₹{instantCost.costPerUnit.toFixed(2)} / finished unit
                      </span>
                    </div>

                    <div className="flex justify-between items-baseline font-mono">
                      <span className="text-xs text-emerald-300/80">Total Required Material Cost:</span>
                      <span className="text-2xl font-bold text-emerald-400">
                        ₹{instantCost.totalEstimatedCost.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </span>
                    </div>

                    {instantCost.items.length > 0 && (
                      <div className="overflow-x-auto pt-1">
                        <table className="w-full text-left text-[11px] font-mono border-collapse">
                          <thead>
                            <tr className="text-emerald-400/70 border-b border-emerald-900 text-[10px]">
                              <th className="py-1">Material</th>
                              <th className="py-1 text-right">Req / Unit</th>
                              <th className="py-1 text-right">Total Req ({quantity}u)</th>
                              <th className="py-1 text-right">Unit Rate</th>
                              <th className="py-1 text-right">Subtotal</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-emerald-900/40">
                            {instantCost.items.map((item, idx) => (
                              <tr key={idx} className="text-emerald-100">
                                <td className="py-1 font-sans">{item.materialName}</td>
                                <td className="py-1 text-right">{item.qtyPerUnit} {item.unit}</td>
                                <td className="py-1 text-right font-bold">{item.totalQty} {item.unit}</td>
                                <td className="py-1 text-right text-emerald-300">₹{item.unitCost}</td>
                                <td className="py-1 text-right font-bold text-emerald-400">
                                  ₹{item.subtotal.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>

                  <div>
                    <span className="text-xs font-semibold text-zinc-700 block mb-2">Configured Routing & Worker Summary</span>
                    <div className="space-y-1.5 text-xs font-mono">
                      {stepAssignments.map((step) => {
                        const mach = machines.find(m => (m.id || m._id) === step.assignedMachineId);
                        const oper = operators.find(o => (o.id || o._id) === step.assignedOperatorId);
                        return (
                          <div key={step.operationId} className="flex items-center justify-between p-2.5 bg-white border border-zinc-200 rounded-xl">
                            <span className="font-bold text-zinc-800">{step.operationId} • {step.name}</span>
                            <div className="flex items-center gap-3 text-[11px]">
                              <span className="text-zinc-600 flex items-center gap-1">
                                <Cpu className="w-3 h-3 text-zinc-500" />
                                {mach?.machineCode || 'None'} ({mach?.type || step.requiredMachineType})
                              </span>
                              <span className="text-zinc-600 flex items-center gap-1">
                                <HardHat className="w-3 h-3 text-amber-600" />
                                {oper?.name || 'Unassigned'}
                              </span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Navigation Footer */}
            <div className="px-6 py-4 bg-zinc-50 border-t border-zinc-200 flex items-center justify-between">
              {modalPhase > 1 ? (
                <button
                  type="button"
                  onClick={() => {
                    setError(null);
                    setModalPhase((modalPhase - 1) as any);
                  }}
                  className="inline-flex items-center gap-1 px-4 py-2 border border-zinc-200 text-xs font-semibold rounded-lg text-zinc-700 hover:bg-white cursor-pointer"
                >
                  <ArrowLeft className="w-3.5 h-3.5" />
                  Back
                </button>
              ) : (
                <div />
              )}

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 border border-zinc-200 text-xs font-medium rounded-lg text-zinc-700 hover:bg-white cursor-pointer"
                >
                  Cancel
                </button>

                {modalPhase === 1 && (
                  <button
                    type="button"
                    onClick={handleNextStep1}
                    className="inline-flex items-center gap-1 px-4 py-2 bg-zinc-900 text-white rounded-lg text-xs font-semibold hover:bg-zinc-800 shadow-2xs cursor-pointer"
                  >
                    Next: Assign Personnel
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                )}

                {modalPhase === 2 && (
                  <button
                    type="button"
                    onClick={handleNextStep2}
                    className="inline-flex items-center gap-1 px-4 py-2 bg-zinc-900 text-white rounded-lg text-xs font-semibold hover:bg-zinc-800 shadow-2xs cursor-pointer"
                  >
                    Next: Review & Launch
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                )}

                {modalPhase === 3 && (
                  <button
                    type="button"
                    onClick={handleFinalSubmit}
                    className="inline-flex items-center gap-1 px-5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold shadow-xs cursor-pointer"
                  >
                    Create & Schedule Work Order
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* AI Assisted Work Order Creation Modal */}
      <AIWorkOrderModal
        isOpen={isAiModalOpen}
        onClose={() => setIsAiModalOpen(false)}
        onApplyDraftToWizard={handleApplyDraftToWizard}
        onWorkOrderCreated={fetchData}
      />
    </div>
  );
}
