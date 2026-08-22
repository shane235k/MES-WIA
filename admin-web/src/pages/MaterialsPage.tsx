import { useState, useEffect } from 'react';
import { 
  Plus, Edit2, Layers, Box, Bookmark, History, 
  Search, ArrowRight, ArrowDownRight, AlertTriangle, 
  RefreshCw, ShieldCheck, MapPin, PackagePlus, CheckCircle2, Filter
} from 'lucide-react';
import { extractErrorMessage } from '../utils/apiError';

interface MaterialSpecification {
  id?: string;
  _id?: string;
  specificationCode: string;
  name: string;
  category: string;
  grade?: string;
  dimensions?: {
    thicknessMm?: number;
    widthMm?: number;
    lengthMm?: number;
    diameterMm?: number;
    outerDiameterMm?: number;
    wallThicknessMm?: number;
    customAttributes?: Record<string, any>;
  };
  densityGcm3?: number;
  unitOfMeasure: string;
  active: boolean;
}

interface Material {
  id?: string;
  _id?: string;
  materialCode: string;
  name: string;
  unit: string;
  quantityAvailable: number;
  quantityOnHand?: number;
  quantityReserved?: number;
  reorderLevel: number;
  active: boolean;
  specificationId?: string;
  category?: string;
  grade?: string;
  unitCost?: number;
}

interface InventoryLot {
  id?: string;
  _id?: string;
  lotNumber: string;
  materialId: string;
  specificationId?: string;
  quantityOnHand: number;
  quantityReserved: number;
  quantityAvailable?: number;
  unitCost?: number;
  unit: string;
  supplier?: string;
  batchNumber?: string;
  heatNumber?: string;
  location: string;
  receivedDate: string;
  expiryDate?: string;
  status: 'AVAILABLE' | 'QUARANTINED' | 'EXPIRED' | 'DEPLETED';
}

interface MaterialReservation {
  id?: string;
  _id?: string;
  workOrderId: string;
  workOrderCode: string;
  operationId: string;
  materialId: string;
  lotId: string;
  lotNumber: string;
  quantityReserved: number;
  quantityConsumed: number;
  status: 'RESERVED' | 'CONSUMED' | 'RELEASED';
  createdAt: string;
}

interface MaterialTransaction {
  id?: string;
  _id?: string;
  transactionId: string;
  transactionType: string;
  materialId: string;
  lotNumber: string;
  workOrderCode?: string;
  operationId?: string;
  quantity: number;
  previousBalance: number;
  resultingBalance: number;
  actorId: string;
  timestamp: string;
  notes?: string;
  scrapReason?: string;
}

const MATERIAL_CATEGORIES = [
  'ALL',
  'SHEET',
  'ROD',
  'BAR',
  'TUBE',
  'WIRE',
  'FASTENER',
  'POWDER',
  'LIQUID',
  'CUSTOM'
];

export default function MaterialsPage() {
  const [activeTab, setActiveTab] = useState<'CATALOG' | 'SPECS' | 'LOTS' | 'RESERVATIONS' | 'LEDGER' | 'TRACE'>('CATALOG');
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');
  
  // Data states
  const [materials, setMaterials] = useState<Material[]>([]);
  const [specs, setSpecs] = useState<MaterialSpecification[]>([]);
  const [lots, setLots] = useState<InventoryLot[]>([]);
  const [reservations, setReservations] = useState<MaterialReservation[]>([]);
  const [transactions, setTransactions] = useState<MaterialTransaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Material Modal
  const [isMatModalOpen, setIsMatModalOpen] = useState(false);
  const [editingMaterial, setEditingMaterial] = useState<Material | null>(null);
  const [matCode, setMatCode] = useState('');
  const [matName, setMatName] = useState('');
  const [matUnit, setMatUnit] = useState('sheets');
  const [matReorder, setMatReorder] = useState<number>(10);
  const [matSpecId, setMatSpecId] = useState('');
  const [matUnitCost, setMatUnitCost] = useState<string>('500');
  const [matActive, setMatActive] = useState(true);

  // Specification Modal
  const [isSpecModalOpen, setIsSpecModalOpen] = useState(false);
  const [editingSpec, setEditingSpec] = useState<MaterialSpecification | null>(null);
  const [specCode, setSpecCode] = useState('');
  const [specName, setSpecName] = useState('');
  const [specCategory, setSpecCategory] = useState('SHEET');
  const [specGrade, setSpecGrade] = useState('');
  const [specThickness, setSpecThickness] = useState<string>('');
  const [specWidth, setSpecWidth] = useState<string>('');
  const [specLength, setSpecLength] = useState<string>('');
  const [specDiameter, setSpecDiameter] = useState<string>('');
  const [specDensity, setSpecDensity] = useState<string>('');
  const [specUnit, setSpecUnit] = useState('sheets');

  // Lot Modal (Receive / Create brand new lot)
  const [isLotModalOpen, setIsLotModalOpen] = useState(false);
  const [lotNumber, setLotNumber] = useState('');
  const [lotMatId, setLotMatId] = useState('');
  const [lotSpecId, setLotSpecId] = useState('');
  const [lotQty, setLotQty] = useState<number>(100);
  const [lotSupplier, setLotSupplier] = useState('');
  const [lotBatch, setLotBatch] = useState('');
  const [lotHeat, setLotHeat] = useState('');
  const [lotUnitCost, setLotUnitCost] = useState<string>('');
  const [lotLocation, setLotLocation] = useState('Warehouse Bay A - Rack 01');

  // Restock Existing Lot / Material Modal
  const [isRestockModalOpen, setIsRestockModalOpen] = useState(false);
  const [restockMaterial, setRestockMaterial] = useState<Material | null>(null);
  const [restockLot, setRestockLot] = useState<InventoryLot | null>(null);
  const [restockMode, setRestockMode] = useState<'TOP_UP' | 'NEW_BATCH'>('TOP_UP');
  const [restockQty, setRestockQty] = useState<number>(50);
  const [restockUnitCost, setRestockUnitCost] = useState<string>('');
  const [restockSupplier, setRestockSupplier] = useState('');
  const [restockNotes, setRestockNotes] = useState('');

  // Lot Adjust Modal
  const [adjustLot, setAdjustLot] = useState<InventoryLot | null>(null);
  const [adjustNewQty, setAdjustNewQty] = useState<number>(0);
  const [adjustReason, setAdjustReason] = useState('');

  // Traceability lookup state
  const [traceLotNumber, setTraceLotNumber] = useState('');
  const [traceWoId, setTraceWoId] = useState('');
  const [traceForwardResult, setTraceForwardResult] = useState<any | null>(null);
  const [traceBackwardResult, setTraceBackwardResult] = useState<any | null>(null);
  const [traceLoading, setTraceLoading] = useState(false);

  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  const fetchData = async () => {
    try {
      setLoading(true);
      const [mRes, sRes, lRes, rRes, tRes] = await Promise.all([
        fetch(`${API_URL}/api/materials`),
        fetch(`${API_URL}/api/materials/specifications`),
        fetch(`${API_URL}/api/inventory/lots`),
        fetch(`${API_URL}/api/inventory/reservations`),
        fetch(`${API_URL}/api/inventory/transactions`)
      ]);

      if (mRes.ok) {
        const d = await mRes.json();
        setMaterials(Array.isArray(d) ? d : []);
      }
      if (sRes.ok) {
        const d = await sRes.json();
        setSpecs(Array.isArray(d) ? d : []);
      }
      if (lRes.ok) {
        const d = await lRes.json();
        setLots(Array.isArray(d) ? d : []);
      }
      if (rRes.ok) {
        const d = await rRes.json();
        setReservations(Array.isArray(d) ? d : []);
      }
      if (tRes.ok) {
        const d = await tRes.json();
        setTransactions(Array.isArray(d) ? d : []);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to fetch inventory data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const showSuccess = (msg: string) => {
    setSuccessMsg(msg);
    setTimeout(() => setSuccessMsg(null), 4000);
  };

  // Material Save Handler
  const handleSaveMaterial = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const selectedSpec = specs.find(s => (s.id || s._id) === matSpecId);
    const payload = {
      materialCode: matCode,
      name: matName,
      unit: matUnit,
      unitCost: matUnitCost ? Number(matUnitCost) : undefined,
      reorderLevel: Number(matReorder),
      specificationId: matSpecId || undefined,
      category: selectedSpec?.category || 'SHEET',
      grade: selectedSpec?.grade || undefined,
      active: matActive
    };

    const url = editingMaterial
      ? `${API_URL}/api/materials/${editingMaterial.id || editingMaterial._id}`
      : `${API_URL}/api/materials`;
    const method = editingMaterial ? 'PUT' : 'POST';

    try {
      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        const d = await res.json();
        throw new Error(extractErrorMessage(d, 'Failed to save material'));
      }
      setIsMatModalOpen(false);
      showSuccess(`Material ${matCode} saved successfully.`);
      fetchData();
    } catch (err: any) {
      setError(err.message);
    }
  };

  // Specification Save Handler
  const handleSaveSpec = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const payload = {
      specificationCode: specCode,
      name: specName,
      category: specCategory,
      grade: specGrade || undefined,
      dimensions: {
        thicknessMm: specThickness ? Number(specThickness) : undefined,
        widthMm: specWidth ? Number(specWidth) : undefined,
        lengthMm: specLength ? Number(specLength) : undefined,
        diameterMm: specDiameter ? Number(specDiameter) : undefined
      },
      densityGcm3: specDensity ? Number(specDensity) : undefined,
      unitOfMeasure: specUnit,
      active: true
    };

    const url = editingSpec
      ? `${API_URL}/api/materials/specifications/${editingSpec.id || editingSpec._id}`
      : `${API_URL}/api/materials/specifications`;
    const method = editingSpec ? 'PUT' : 'POST';

    try {
      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        const d = await res.json();
        throw new Error(extractErrorMessage(d, 'Failed to save specification'));
      }
      setIsSpecModalOpen(false);
      showSuccess(`Specification ${specCode} saved successfully.`);
      fetchData();
    } catch (err: any) {
      setError(err.message);
    }
  };

  // Lot Create Handler (Brand new physical lot)
  const handleCreateLot = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const payload = {
      lotNumber,
      materialId: lotMatId,
      specificationId: lotSpecId || undefined,
      quantityOnHand: Number(lotQty),
      unitCost: lotUnitCost ? Number(lotUnitCost) : undefined,
      supplier: lotSupplier || undefined,
      batchNumber: lotBatch || undefined,
      heatNumber: lotHeat || undefined,
      location: lotLocation,
      status: 'AVAILABLE'
    };

    try {
      const res = await fetch(`${API_URL}/api/inventory/lots`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        const d = await res.json();
        throw new Error(extractErrorMessage(d, 'Failed to create lot'));
      }
      setIsLotModalOpen(false);
      showSuccess(`Received new lot ${lotNumber} (+${lotQty} units).`);
      fetchData();
    } catch (err: any) {
      setError(err.message);
    }
  };

  // Open Restock Modal for a Specific Material
  const handleOpenRestockForMaterial = (mat: Material) => {
    setRestockMaterial(mat);
    const matId = mat.id || mat._id;
    const existingLotsForMat = lots.filter(l => l.materialId === matId);
    
    if (existingLotsForMat.length > 0) {
      setRestockLot(existingLotsForMat[0]);
      setRestockMode('TOP_UP');
    } else {
      setRestockLot(null);
      setRestockMode('NEW_BATCH');
    }
    setRestockQty(50);
    setRestockUnitCost(mat.unitCost ? String(mat.unitCost) : '500');
    setRestockSupplier('');
    setRestockNotes('');
    setIsRestockModalOpen(true);
  };

  // Open Restock Modal for a Specific Lot directly
  const handleOpenRestockForLot = (lot: InventoryLot) => {
    const mat = materials.find(m => (m.id || m._id) === lot.materialId) || null;
    setRestockMaterial(mat);
    setRestockLot(lot);
    setRestockMode('TOP_UP');
    setRestockQty(50);
    setRestockUnitCost(lot.unitCost ? String(lot.unitCost) : (mat?.unitCost ? String(mat.unitCost) : ''));
    setRestockSupplier(lot.supplier || '');
    setRestockNotes('');
    setIsRestockModalOpen(true);
  };

  // Submit Restock Handler (either receives stock into existing lot or creates new batch)
  const handleSubmitRestock = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    try {
      if (restockMode === 'TOP_UP' && restockLot) {
        const lotId = restockLot.id || restockLot._id;
        const res = await fetch(`${API_URL}/api/inventory/lots/${lotId}/receive`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            quantity: Number(restockQty),
            unitCost: restockUnitCost ? Number(restockUnitCost) : undefined,
            supplier: restockSupplier || undefined,
            notes: restockNotes || `Restocked inventory lot ${restockLot.lotNumber}`,
            actorId: 'ADMIN'
          })
        });

        if (!res.ok) {
          const d = await res.json();
          throw new Error(extractErrorMessage(d, 'Failed to restock lot'));
        }
        showSuccess(`Restocked +${restockQty} ${restockLot.unit} into lot ${restockLot.lotNumber}. Status is now AVAILABLE.`);
      } else {
        // Create new lot batch
        const matId = restockMaterial ? (restockMaterial.id || restockMaterial._id) : (materials[0]?.id || materials[0]?._id);
        const mat = materials.find(m => (m.id || m._id) === matId);
        const newLotNum = `LOT-${new Date().getFullYear()}-${Math.floor(1000 + Math.random() * 9000)}`;
        
        const payload = {
          lotNumber: newLotNum,
          materialId: matId,
          specificationId: mat?.specificationId || undefined,
          quantityOnHand: Number(restockQty),
          unitCost: restockUnitCost ? Number(restockUnitCost) : (mat?.unitCost || undefined),
          supplier: restockSupplier || 'Internal Restock',
          batchNumber: `BATCH-${Date.now().toString().slice(-4)}`,
          heatNumber: `HEAT-RESTOCK-${Date.now().toString().slice(-4)}`,
          location: 'Warehouse Bay A - Rack 01',
          status: 'AVAILABLE'
        };

        const res = await fetch(`${API_URL}/api/inventory/lots`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        if (!res.ok) {
          const d = await res.json();
          throw new Error(extractErrorMessage(d, 'Failed to create new batch'));
        }
        showSuccess(`Received new batch lot ${newLotNum} (+${restockQty} ${mat?.unit || 'units'}).`);
      }

      setIsRestockModalOpen(false);
      fetchData();
    } catch (err: any) {
      setError(err.message);
    }
  };

  // Lot Adjust Handler
  const handleAdjustLot = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!adjustLot) return;
    try {
      const res = await fetch(`${API_URL}/api/inventory/lots/${adjustLot.id || adjustLot._id}/adjust`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          newQuantityOnHand: Number(adjustNewQty),
          reason: adjustReason || 'Physical inventory cycle count adjustment',
          actorId: 'ADMIN'
        })
      });
      if (!res.ok) {
        const d = await res.json();
        throw new Error(extractErrorMessage(d, 'Failed to adjust stock'));
      }
      setAdjustLot(null);
      showSuccess(`Adjusted lot ${adjustLot.lotNumber} balance.`);
      fetchData();
    } catch (err: any) {
      setError(err.message);
    }
  };

  // Traceability Handlers
  const handleForwardTrace = async () => {
    if (!traceLotNumber) return;
    try {
      setTraceLoading(true);
      setError(null);
      const res = await fetch(`${API_URL}/api/inventory/trace/forward/${encodeURIComponent(traceLotNumber)}`);
      if (!res.ok) {
        const d = await res.json();
        throw new Error(extractErrorMessage(d, 'Forward trace failed'));
      }
      setTraceForwardResult(await res.json());
    } catch (err: any) {
      setError(err.message);
    } finally {
      setTraceLoading(false);
    }
  };

  const handleBackwardTrace = async () => {
    if (!traceWoId) return;
    try {
      setTraceLoading(true);
      setError(null);
      const res = await fetch(`${API_URL}/api/inventory/trace/backward/${encodeURIComponent(traceWoId)}`);
      if (!res.ok) {
        const d = await res.json();
        throw new Error(extractErrorMessage(d, 'Backward trace failed'));
      }
      setTraceBackwardResult(await res.json());
    } catch (err: any) {
      setError(err.message);
    } finally {
      setTraceLoading(false);
    }
  };

  // Filtered materials & specs
  const filteredMaterials = selectedCategory === 'ALL'
    ? materials
    : materials.filter(m => (m.category || 'SHEET').toUpperCase() === selectedCategory.toUpperCase());

  const filteredSpecs = selectedCategory === 'ALL'
    ? specs
    : specs.filter(s => s.category.toUpperCase() === selectedCategory.toUpperCase());

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-900 flex items-center gap-2">
            <Box className="w-6 h-6 text-zinc-900" />
            Materials & Inventory Management
          </h1>
          <p className="text-xs text-zinc-500 mt-1">
            Physical stock lots, FIFO/FEFO allocation, standard material costing, and append-only traceability.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => fetchData()}
            disabled={loading}
            className="p-2 border border-zinc-200 hover:bg-zinc-50 rounded-lg text-zinc-600 transition-colors shadow-2xs cursor-pointer disabled:opacity-50"
            title="Refresh Inventory"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
          
          {activeTab === 'CATALOG' && (
            <>
              <button
                onClick={() => {
                  setEditingMaterial(null);
                  setMatCode(`MAT-${Date.now().toString().slice(-4)}`);
                  setMatName('');
                  setMatUnit('sheets');
                  setMatReorder(20);
                  setMatSpecId(specs[0]?.id || specs[0]?._id || '');
                  setMatUnitCost('500');
                  setMatActive(true);
                  setIsMatModalOpen(true);
                }}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-zinc-700 bg-white border border-zinc-300 hover:bg-zinc-50 rounded-lg transition-colors shadow-2xs cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5" />
                Define Material
              </button>
              <button
                onClick={() => {
                  setRestockMaterial(materials[0] || null);
                  setRestockLot(lots[0] || null);
                  setRestockMode('TOP_UP');
                  setRestockQty(100);
                  setRestockUnitCost('');
                  setRestockSupplier('');
                  setRestockNotes('');
                  setIsRestockModalOpen(true);
                }}
                className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg transition-colors shadow-2xs cursor-pointer"
              >
                <PackagePlus className="w-3.5 h-3.5" />
                Restock Material
              </button>
            </>
          )}

          {activeTab === 'SPECS' && (
            <button
              onClick={() => {
                setEditingSpec(null);
                setSpecCode(`SPEC-${Date.now().toString().slice(-4)}`);
                setSpecName('');
                setSpecCategory('SHEET');
                setSpecGrade('');
                setSpecThickness('');
                setSpecWidth('');
                setSpecLength('');
                setSpecDiameter('');
                setSpecDensity('');
                setSpecUnit('sheets');
                setIsSpecModalOpen(true);
              }}
              className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold text-white bg-zinc-900 hover:bg-zinc-800 rounded-lg transition-colors shadow-2xs cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" />
              Add Specification
            </button>
          )}

          {activeTab === 'LOTS' && (
            <button
              onClick={() => {
                setLotNumber(`LOT-${new Date().getFullYear()}-${Math.floor(1000 + Math.random() * 9000)}`);
                setLotMatId(materials[0]?.id || materials[0]?._id || '');
                setLotSpecId(materials[0]?.specificationId || '');
                setLotQty(100);
                setLotSupplier('Apex Industrial Supplies');
                setLotBatch(`BATCH-${Math.floor(1000 + Math.random() * 9000)}`);
                setLotHeat(`HEAT-HT-${Math.floor(1000 + Math.random() * 9000)}`);
                setLotLocation('Warehouse Bay A - Rack 01');
                setLotUnitCost(materials[0]?.unitCost ? String(materials[0].unitCost) : '500');
                setIsLotModalOpen(true);
              }}
              className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold text-white bg-zinc-900 hover:bg-zinc-800 rounded-lg transition-colors shadow-2xs cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" />
              Receive New Batch/Lot
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="p-3 border border-rose-200 bg-rose-50 text-rose-800 rounded-xl text-xs flex items-center justify-between font-mono">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-rose-400 hover:text-rose-700">✕</button>
        </div>
      )}

      {successMsg && (
        <div className="p-3 border border-emerald-200 bg-emerald-50 text-emerald-800 rounded-xl text-xs flex items-center justify-between font-mono">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{successMsg}</span>
          </div>
          <button onClick={() => setSuccessMsg(null)} className="text-emerald-400 hover:text-emerald-700">✕</button>
        </div>
      )}

      {/* Tab Navigation */}
      <div className="flex items-center gap-2 bg-white p-1.5 rounded-xl border border-zinc-200 shadow-2xs overflow-x-auto">
        {[
          { key: 'CATALOG', label: 'Material Catalog', icon: Box, count: materials.length },
          { key: 'SPECS', label: 'Specifications', icon: Layers, count: specs.length },
          { key: 'LOTS', label: 'Inventory Lots', icon: Bookmark, count: lots.length },
          { key: 'RESERVATIONS', label: 'Active Reservations', icon: ShieldCheck, count: reservations.filter(r => r.status === 'RESERVED').length },
          { key: 'LEDGER', label: 'Transaction Ledger', icon: History, count: transactions.length },
          { key: 'TRACE', label: 'Genealogy & Traceability', icon: Search, count: null },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key as any)}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-medium transition-all whitespace-nowrap cursor-pointer ${
                isActive
                  ? 'bg-zinc-900 text-white font-semibold shadow-2xs'
                  : 'text-zinc-600 hover:text-zinc-900 hover:bg-zinc-100'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{tab.label}</span>
              {tab.count !== null && (
                <span className={`px-1.5 py-0.2 rounded-full text-[10px] font-mono ${
                  isActive ? 'bg-zinc-700 text-white' : 'bg-zinc-200 text-zinc-600'
                }`}>
                  {tab.count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Category Filter Pills (for Catalog & Specs) */}
      {(activeTab === 'CATALOG' || activeTab === 'SPECS') && (
        <div className="flex items-center gap-1.5 bg-zinc-50 p-2 rounded-xl border border-zinc-200 overflow-x-auto text-xs">
          <div className="flex items-center gap-1 text-zinc-500 font-semibold px-2">
            <Filter className="w-3.5 h-3.5" />
            <span>Category:</span>
          </div>
          {MATERIAL_CATEGORIES.map((cat) => {
            const count = cat === 'ALL'
              ? materials.length
              : materials.filter(m => (m.category || 'SHEET').toUpperCase() === cat).length;
            const isSelected = selectedCategory === cat;
            return (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={`px-3 py-1 rounded-lg text-[11px] font-mono font-bold transition-all cursor-pointer whitespace-nowrap ${
                  isSelected
                    ? 'bg-zinc-900 text-white shadow-2xs'
                    : 'bg-white text-zinc-600 hover:bg-zinc-200 border border-zinc-200'
                }`}
              >
                {cat} {cat !== 'ALL' && `(${count})`}
              </button>
            );
          })}
        </div>
      )}

      {/* Tab 1: Material Catalog */}
      {activeTab === 'CATALOG' && (
        <div className="bg-white border border-zinc-200 rounded-2xl overflow-hidden shadow-2xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-zinc-100 bg-zinc-50/70 text-zinc-500 font-mono text-[11px]">
                  <th className="py-3 px-4 font-semibold">Material Code</th>
                  <th className="py-3 px-4 font-semibold">Name & Category</th>
                  <th className="py-3 px-4 font-semibold">Form / Grade</th>
                  <th className="py-3 px-4 font-semibold">On-Hand</th>
                  <th className="py-3 px-4 font-semibold">Reserved</th>
                  <th className="py-3 px-4 font-semibold">Available</th>
                  <th className="py-3 px-4 font-semibold text-right">Std Unit Cost</th>
                  <th className="py-3 px-4 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {filteredMaterials.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="py-8 text-center text-zinc-400 font-mono">
                      No materials found in category '{selectedCategory}'.
                    </td>
                  </tr>
                ) : (
                  filteredMaterials.map((mat) => {
                    const onHand = mat.quantityOnHand ?? mat.quantityAvailable ?? 0;
                    const reserved = mat.quantityReserved ?? 0;
                    const avail = mat.quantityAvailable ?? Math.max(0, onHand - reserved);
                    const isLow = avail <= mat.reorderLevel;
                    const isDepleted = onHand <= 0;
                    const matLots = lots.filter(l => l.materialId === (mat.id || mat._id));

                    return (
                      <tr key={mat.id || mat._id} className={`hover:bg-zinc-50/50 transition-colors ${isDepleted ? 'bg-rose-50/20' : ''}`}>
                        <td className="py-3 px-4 font-mono font-bold text-zinc-900">
                          {mat.materialCode}
                        </td>
                        <td className="py-3 px-4">
                          <div className="font-semibold text-zinc-800">{mat.name}</div>
                          <div className="text-[11px] text-zinc-400 font-mono flex items-center gap-1.5 mt-0.5">
                            <span>Unit: {mat.unit}</span>
                            <span>•</span>
                            <span>{matLots.length} lot(s) tracked</span>
                          </div>
                        </td>
                        <td className="py-3 px-4 font-mono text-zinc-600">
                          <span className="px-2 py-0.5 rounded bg-zinc-100 border border-zinc-200 text-[11px] font-bold">
                            {mat.category || 'SHEET'} • {mat.grade || 'Standard'}
                          </span>
                        </td>
                        <td className="py-3 px-4 font-mono font-bold text-zinc-900">
                          {onHand} {mat.unit}
                        </td>
                        <td className="py-3 px-4 font-mono text-amber-700 font-semibold">
                          {reserved} {mat.unit}
                        </td>
                        <td className="py-3 px-4 font-mono">
                          <span className={`px-2 py-0.5 rounded font-bold ${
                            isDepleted 
                              ? 'bg-rose-100 text-rose-900 border border-rose-300' 
                              : isLow 
                              ? 'bg-amber-100 text-amber-800 border border-amber-200' 
                              : 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                          }`}>
                            {avail} {mat.unit} {isDepleted ? '(DEPLETED)' : isLow ? '(LOW)' : ''}
                          </span>
                        </td>
                        <td className="py-3 px-4 font-mono text-right text-zinc-900 font-bold">
                          {mat.unitCost !== null && mat.unitCost !== undefined ? `₹${mat.unitCost.toLocaleString('en-IN')}` : '—'}
                        </td>
                        <td className="py-3 px-4 text-right space-x-1.5">
                          <button
                            onClick={() => handleOpenRestockForMaterial(mat)}
                            className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-bold text-emerald-800 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 rounded-md transition-colors cursor-pointer"
                            title="Restock or Add Stock to this material"
                          >
                            <PackagePlus className="w-3 h-3" />
                            Restock
                          </button>
                          <button
                            onClick={() => {
                              setEditingMaterial(mat);
                              setMatCode(mat.materialCode);
                              setMatName(mat.name);
                              setMatUnit(mat.unit);
                              setMatUnitCost(mat.unitCost ? String(mat.unitCost) : '');
                              setMatReorder(mat.reorderLevel);
                              setMatSpecId(mat.specificationId || '');
                              setMatActive(mat.active);
                              setIsMatModalOpen(true);
                            }}
                            className="p-1 text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100 rounded-md transition-colors cursor-pointer"
                            title="Edit Material"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 2: Specifications */}
      {activeTab === 'SPECS' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredSpecs.map((spec) => (
            <div key={spec.id || spec._id} className="bg-white border border-zinc-200 rounded-2xl p-4 shadow-2xs hover:shadow-md transition-all space-y-3">
              <div className="flex items-start justify-between">
                <div>
                  <span className="font-mono text-xs font-bold text-zinc-900 bg-zinc-100 px-2 py-0.5 rounded border border-zinc-200">
                    {spec.specificationCode}
                  </span>
                  <h3 className="font-bold text-zinc-900 text-sm mt-1.5">{spec.name}</h3>
                </div>
                <span className="text-[10px] font-mono font-bold uppercase px-2 py-0.5 rounded bg-blue-50 text-blue-800 border border-blue-200">
                  {spec.category}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2 text-xs font-mono bg-zinc-50 p-2.5 rounded-xl border border-zinc-200/80">
                <div>
                  <span className="text-zinc-400 text-[10px] block">Alloy / Grade:</span>
                  <strong className="text-zinc-900">{spec.grade || 'Unspecified'}</strong>
                </div>
                <div>
                  <span className="text-zinc-400 text-[10px] block">Unit:</span>
                  <strong className="text-zinc-900">{spec.unitOfMeasure}</strong>
                </div>
                {spec.densityGcm3 && (
                  <div>
                    <span className="text-zinc-400 text-[10px] block">Density:</span>
                    <strong className="text-zinc-900">{spec.densityGcm3} g/cm³</strong>
                  </div>
                )}
                {spec.dimensions?.thicknessMm && (
                  <div>
                    <span className="text-zinc-400 text-[10px] block">Thickness:</span>
                    <strong className="text-zinc-900">{spec.dimensions.thicknessMm} mm</strong>
                  </div>
                )}
                {spec.dimensions?.diameterMm && (
                  <div>
                    <span className="text-zinc-400 text-[10px] block">Diameter:</span>
                    <strong className="text-zinc-900">{spec.dimensions.diameterMm} mm</strong>
                  </div>
                )}
                {spec.dimensions?.lengthMm && (
                  <div>
                    <span className="text-zinc-400 text-[10px] block">Length:</span>
                    <strong className="text-zinc-900">{spec.dimensions.lengthMm} mm</strong>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Tab 3: Inventory Lots */}
      {activeTab === 'LOTS' && (
        <div className="bg-white border border-zinc-200 rounded-2xl overflow-hidden shadow-2xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-zinc-100 bg-zinc-50/70 text-zinc-500 font-mono text-[11px]">
                  <th className="py-3 px-4 font-semibold">Lot Number</th>
                  <th className="py-3 px-4 font-semibold">Material Code</th>
                  <th className="py-3 px-4 font-semibold">Supplier / Heat / Batch</th>
                  <th className="py-3 px-4 font-semibold">Storage Location</th>
                  <th className="py-3 px-4 font-semibold">On-Hand</th>
                  <th className="py-3 px-4 font-semibold">Reserved</th>
                  <th className="py-3 px-4 font-semibold">Available</th>
                  <th className="py-3 px-4 font-semibold text-right">Unit Cost</th>
                  <th className="py-3 px-4 font-semibold">Status</th>
                  <th className="py-3 px-4 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {lots.map((lot) => {
                  const mat = materials.find(m => (m.id || m._id) === lot.materialId);
                  const avail = Math.max(0, lot.quantityOnHand - lot.quantityReserved);
                  const isDepleted = lot.quantityOnHand <= 0 || lot.status === 'DEPLETED';

                  return (
                    <tr key={lot.id || lot._id} className={`hover:bg-zinc-50/50 transition-colors ${isDepleted ? 'bg-rose-50/30' : ''}`}>
                      <td className="py-3 px-4 font-mono font-bold text-zinc-900">
                        {lot.lotNumber}
                      </td>
                      <td className="py-3 px-4 font-mono text-zinc-700">
                        <span className="font-bold text-zinc-900">{mat?.materialCode || lot.materialId}</span>
                        <span className="text-[10px] text-zinc-400 block">{mat?.name}</span>
                      </td>
                      <td className="py-3 px-4">
                        <div className="text-zinc-800 font-medium">{lot.supplier || 'Internal Stock'}</div>
                        <div className="text-[10px] font-mono text-zinc-400">Heat: {lot.heatNumber || 'N/A'} • Batch: {lot.batchNumber || 'N/A'}</div>
                      </td>
                      <td className="py-3 px-4 font-mono text-zinc-600">
                        <span className="flex items-center gap-1">
                          <MapPin className="w-3 h-3 text-zinc-400" />
                          {lot.location}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-mono font-bold text-zinc-900">
                        {lot.quantityOnHand} {lot.unit}
                      </td>
                      <td className="py-3 px-4 font-mono text-amber-700 font-semibold">
                        {lot.quantityReserved} {lot.unit}
                      </td>
                      <td className="py-3 px-4 font-mono font-bold text-emerald-700">
                        {avail} {lot.unit}
                      </td>
                      <td className="py-3 px-4 font-mono text-right text-zinc-800 font-semibold">
                        {lot.unitCost !== null && lot.unitCost !== undefined ? `₹${lot.unitCost.toLocaleString('en-IN')}` : '—'}
                      </td>
                      <td className="py-3 px-4">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                          lot.status === 'AVAILABLE' ? 'bg-emerald-100 text-emerald-800' :
                          lot.status === 'DEPLETED' ? 'bg-rose-100 text-rose-800 border border-rose-200' :
                          'bg-amber-100 text-amber-800'
                        }`}>
                          {lot.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right space-x-1.5">
                        <button
                          onClick={() => handleOpenRestockForLot(lot)}
                          className="px-2.5 py-1 text-[11px] font-bold text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 rounded-md transition-colors cursor-pointer inline-flex items-center gap-1"
                          title="Restock this lot with additional quantity"
                        >
                          <PackagePlus className="w-3 h-3" />
                          + Restock
                        </button>
                        <button
                          onClick={() => {
                            setAdjustLot(lot);
                            setAdjustNewQty(lot.quantityOnHand);
                            setAdjustReason('');
                          }}
                          className="px-2 py-1 text-[11px] font-semibold text-zinc-700 bg-zinc-100 hover:bg-zinc-200 rounded-md transition-colors cursor-pointer"
                        >
                          Adjust
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 4: Active Reservations */}
      {activeTab === 'RESERVATIONS' && (
        <div className="bg-white border border-zinc-200 rounded-2xl overflow-hidden shadow-2xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-zinc-100 bg-zinc-50/70 text-zinc-500 font-mono text-[11px]">
                  <th className="py-3 px-4 font-semibold">Work Order</th>
                  <th className="py-3 px-4 font-semibold">Operation ID</th>
                  <th className="py-3 px-4 font-semibold">Allocated Lot</th>
                  <th className="py-3 px-4 font-semibold">Quantity Reserved</th>
                  <th className="py-3 px-4 font-semibold">Quantity Consumed</th>
                  <th className="py-3 px-4 font-semibold">Status</th>
                  <th className="py-3 px-4 font-semibold">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {reservations.map((res) => (
                  <tr key={res.id || res._id} className="hover:bg-zinc-50/50 transition-colors">
                    <td className="py-3 px-4 font-mono font-bold text-zinc-900">
                      {res.workOrderCode}
                    </td>
                    <td className="py-3 px-4 font-mono text-zinc-700">
                      {res.operationId}
                    </td>
                    <td className="py-3 px-4 font-mono font-semibold text-blue-700">
                      {res.lotNumber}
                    </td>
                    <td className="py-3 px-4 font-mono font-bold text-amber-700">
                      {res.quantityReserved}
                    </td>
                    <td className="py-3 px-4 font-mono font-bold text-emerald-700">
                      {res.quantityConsumed}
                    </td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-blue-50 text-blue-800 border border-blue-200">
                        {res.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-mono text-zinc-400 text-[11px]">
                      {new Date(res.createdAt).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 5: Transaction Ledger */}
      {activeTab === 'LEDGER' && (
        <div className="bg-white border border-zinc-200 rounded-2xl overflow-hidden shadow-2xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-zinc-100 bg-zinc-50/70 text-zinc-500 font-mono text-[11px]">
                  <th className="py-3 px-4 font-semibold">Timestamp</th>
                  <th className="py-3 px-4 font-semibold">Type</th>
                  <th className="py-3 px-4 font-semibold">Lot #</th>
                  <th className="py-3 px-4 font-semibold">Delta Qty</th>
                  <th className="py-3 px-4 font-semibold">Balances (Prev → Next)</th>
                  <th className="py-3 px-4 font-semibold">Work Order / Op</th>
                  <th className="py-3 px-4 font-semibold">Actor / Notes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {transactions.map((tx) => {
                  const isPositive = ['RECEIPT', 'ADJUSTMENT_INCREASE', 'SCRAP_RETURN'].includes(tx.transactionType);
                  return (
                    <tr key={tx.id || tx._id} className="hover:bg-zinc-50/50 transition-colors font-mono">
                      <td className="py-3 px-4 text-zinc-500 text-[11px]">
                        {new Date(tx.timestamp).toLocaleString()}
                      </td>
                      <td className="py-3 px-4">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          tx.transactionType === 'RECEIPT' ? 'bg-emerald-100 text-emerald-800' :
                          tx.transactionType === 'CONSUMPTION' ? 'bg-blue-100 text-blue-800' :
                          tx.transactionType === 'SCRAP' ? 'bg-rose-100 text-rose-800' :
                          'bg-zinc-100 text-zinc-800'
                        }`}>
                          {tx.transactionType}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-bold text-zinc-900">
                        {tx.lotNumber}
                      </td>
                      <td className={`py-3 px-4 font-bold ${isPositive ? 'text-emerald-700' : 'text-rose-700'}`}>
                        {isPositive ? '+' : '-'}{tx.quantity}
                      </td>
                      <td className="py-3 px-4 text-zinc-600 text-[11px]">
                        {tx.previousBalance} → <strong className="text-zinc-900">{tx.resultingBalance}</strong>
                      </td>
                      <td className="py-3 px-4 text-zinc-700">
                        {tx.workOrderCode || '—'} {tx.operationId ? `(${tx.operationId})` : ''}
                      </td>
                      <td className="py-3 px-4 text-zinc-600">
                        <div className="font-semibold text-zinc-800">{tx.actorId}</div>
                        <div className="text-[10px] text-zinc-400 font-sans truncate max-w-xs">{tx.notes || '—'}</div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 6: Traceability Lookup */}
      {activeTab === 'TRACE' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Forward Trace */}
            <div className="bg-white border border-zinc-200 rounded-2xl p-5 shadow-2xs space-y-3">
              <h3 className="font-bold text-sm text-zinc-900 flex items-center gap-2">
                <ArrowRight className="w-4 h-4 text-zinc-900" />
                Forward Traceability (Lot → Work Orders)
              </h3>
              <p className="text-xs text-zinc-500">
                Identify which Work Orders and operations consumed physical material from a specific lot number.
              </p>
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="e.g. LOT-2026-SS-001"
                  value={traceLotNumber}
                  onChange={(e) => setTraceLotNumber(e.target.value.toUpperCase())}
                  className="flex-1 px-3 py-1.5 border border-zinc-300 rounded-lg text-xs font-mono"
                />
                <button
                  onClick={handleForwardTrace}
                  disabled={traceLoading || !traceLotNumber}
                  className="px-3.5 py-1.5 bg-zinc-900 text-white font-semibold text-xs rounded-lg hover:bg-zinc-800 disabled:opacity-50 cursor-pointer"
                >
                  Trace Lot
                </button>
              </div>

              {traceForwardResult && (
                <div className="mt-4 p-3 bg-zinc-50 rounded-xl border border-zinc-200 space-y-2 text-xs font-mono">
                  <div className="font-bold text-zinc-900">Trace Results for {traceForwardResult.lotNumber}:</div>
                  <div className="text-zinc-600">Material ID: {traceForwardResult.materialId}</div>
                  <div className="text-zinc-600">Total Consumed: {traceForwardResult.totalQuantityConsumed}</div>
                  <div className="font-semibold text-zinc-800 mt-2">Consumed In Work Orders:</div>
                  <div className="space-y-1">
                    {traceForwardResult.consumedInWorkOrders?.map((c: any, i: number) => (
                      <div key={i} className="p-2 bg-white rounded border border-zinc-200 flex justify-between">
                        <span>WO: <strong>{c.workOrderCode}</strong> ({c.operationId})</span>
                        <span className="text-emerald-700 font-bold">{c.quantity} units</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Backward Trace */}
            <div className="bg-white border border-zinc-200 rounded-2xl p-5 shadow-2xs space-y-3">
              <h3 className="font-bold text-sm text-zinc-900 flex items-center gap-2">
                <ArrowDownRight className="w-4 h-4 text-zinc-900" />
                Backward Traceability (Work Order → Heat/Lots)
              </h3>
              <p className="text-xs text-zinc-500">
                Audit all raw material heats, supplier lot numbers, and specifications built into a completed Work Order.
              </p>
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="e.g. WO-1001"
                  value={traceWoId}
                  onChange={(e) => setTraceWoId(e.target.value)}
                  className="flex-1 px-3 py-1.5 border border-zinc-300 rounded-lg text-xs font-mono"
                />
                <button
                  onClick={handleBackwardTrace}
                  disabled={traceLoading || !traceWoId}
                  className="px-3.5 py-1.5 bg-zinc-900 text-white font-semibold text-xs rounded-lg hover:bg-zinc-800 disabled:opacity-50 cursor-pointer"
                >
                  Trace Work Order
                </button>
              </div>

              {traceBackwardResult && (
                <div className="mt-4 p-3 bg-zinc-50 rounded-xl border border-zinc-200 space-y-2 text-xs font-mono">
                  <div className="font-bold text-zinc-900">Materials In {traceBackwardResult.workOrderCode}:</div>
                  <div className="space-y-1">
                    {traceBackwardResult.consumedMaterials?.map((m: any, i: number) => (
                      <div key={i} className="p-2 bg-white rounded border border-zinc-200 flex justify-between items-center">
                        <div>
                          <div className="font-bold text-zinc-900">{m.materialName} ({m.lotNumber})</div>
                          <div className="text-[10px] text-zinc-400">Supplier: {m.supplier || 'N/A'} • Heat: {m.heatNumber || 'N/A'}</div>
                        </div>
                        <span className="text-emerald-700 font-bold">{m.quantity} {m.unit}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Modal: Define/Edit Material */}
      {isMatModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs">
          <div className="bg-white border border-zinc-200 rounded-2xl w-full max-w-md p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-zinc-100 pb-3">
              <h3 className="font-bold text-sm text-zinc-900">
                {editingMaterial ? 'Edit Material' : 'Define New Material'}
              </h3>
              <button onClick={() => setIsMatModalOpen(false)} className="text-zinc-400 hover:text-zinc-700">✕</button>
            </div>
            <form onSubmit={handleSaveMaterial} className="space-y-3 text-xs">
              <div>
                <label className="block font-semibold text-zinc-700 mb-1">Material Code</label>
                <input
                  type="text"
                  required
                  value={matCode}
                  onChange={(e) => setMatCode(e.target.value.toUpperCase())}
                  className="w-full px-3 py-1.5 border border-zinc-200 rounded-lg font-mono font-bold"
                  placeholder="e.g. ROD-SS316-25MM"
                />
              </div>
              <div>
                <label className="block font-semibold text-zinc-700 mb-1">Material Name</label>
                <input
                  type="text"
                  required
                  value={matName}
                  onChange={(e) => setMatName(e.target.value)}
                  className="w-full px-3 py-1.5 border border-zinc-200 rounded-lg"
                  placeholder="e.g. 25mm SS316 Stainless Steel Round Rod"
                />
              </div>
              <div>
                <label className="block font-semibold text-zinc-700 mb-1">Material Specification</label>
                <select
                  value={matSpecId}
                  onChange={(e) => {
                    setMatSpecId(e.target.value);
                    const s = specs.find(spec => (spec.id || spec._id) === e.target.value);
                    if (s) setMatUnit(s.unitOfMeasure);
                  }}
                  className="w-full px-3 py-1.5 border border-zinc-200 rounded-lg font-mono"
                >
                  <option value="">None / Custom</option>
                  {specs.map((s) => (
                    <option key={s.id || s._id} value={s.id || s._id}>
                      {s.specificationCode} ({s.category}) — {s.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block font-semibold text-zinc-700 mb-1">Stock Unit</label>
                  <input
                    type="text"
                    required
                    value={matUnit}
                    onChange={(e) => setMatUnit(e.target.value)}
                    className="w-full px-3 py-1.5 border border-zinc-200 rounded-lg font-mono"
                    placeholder="sheets, meters, kg, pcs"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-zinc-700 mb-1">Std Unit Cost (₹)</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={matUnitCost}
                    onChange={(e) => setMatUnitCost(e.target.value)}
                    className="w-full px-3 py-1.5 border border-zinc-200 rounded-lg font-mono"
                    placeholder="500.00"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-zinc-700 mb-1">Reorder Level</label>
                  <input
                    type="number"
                    min="0"
                    value={matReorder}
                    onChange={(e) => setMatReorder(Number(e.target.value))}
                    className="w-full px-3 py-1.5 border border-zinc-200 rounded-lg font-mono"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-3 border-t border-zinc-100">
                <button
                  type="button"
                  onClick={() => setIsMatModalOpen(false)}
                  className="px-3 py-1.5 border border-zinc-200 rounded-lg text-zinc-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 bg-zinc-900 text-white font-semibold rounded-lg hover:bg-zinc-800"
                >
                  Save Material
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Add/Edit Specification */}
      {isSpecModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs">
          <div className="bg-white border border-zinc-200 rounded-2xl w-full max-w-md p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-zinc-100 pb-3">
              <h3 className="font-bold text-sm text-zinc-900">
                {editingSpec ? 'Edit Specification' : 'New Material Specification'}
              </h3>
              <button onClick={() => setIsSpecModalOpen(false)} className="text-zinc-400 hover:text-zinc-700">✕</button>
            </div>
            <form onSubmit={handleSaveSpec} className="space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-zinc-700 mb-1">Spec Code</label>
                  <input
                    type="text"
                    required
                    value={specCode}
                    onChange={(e) => setSpecCode(e.target.value.toUpperCase())}
                    className="w-full px-3 py-1.5 border border-zinc-200 rounded-lg font-mono font-bold"
                    placeholder="SPEC-ROD-25MM"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-zinc-700 mb-1">Category / Form</label>
                  <select
                    value={specCategory}
                    onChange={(e) => setSpecCategory(e.target.value)}
                    className="w-full px-3 py-1.5 border border-zinc-200 rounded-lg font-mono"
                  >
                    {MATERIAL_CATEGORIES.filter(c => c !== 'ALL').map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div>
                <label className="block font-semibold text-zinc-700 mb-1">Specification Name</label>
                <input
                  type="text"
                  required
                  value={specName}
                  onChange={(e) => setSpecName(e.target.value)}
                  className="w-full px-3 py-1.5 border border-zinc-200 rounded-lg"
                  placeholder="e.g. SS316 Round Solid Rod (25mm dia)"
                />
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block font-semibold text-zinc-700 mb-1">Alloy / Grade</label>
                  <input
                    type="text"
                    value={specGrade}
                    onChange={(e) => setSpecGrade(e.target.value)}
                    className="w-full px-3 py-1.5 border border-zinc-200 rounded-lg font-mono"
                    placeholder="e.g. SS316, Grade 8.8"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-zinc-700 mb-1">Density (g/cm³)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={specDensity}
                    onChange={(e) => setSpecDensity(e.target.value)}
                    className="w-full px-3 py-1.5 border border-zinc-200 rounded-lg font-mono"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-zinc-700 mb-1">Unit of Measure</label>
                  <input
                    type="text"
                    required
                    value={specUnit}
                    onChange={(e) => setSpecUnit(e.target.value)}
                    className="w-full px-3 py-1.5 border border-zinc-200 rounded-lg font-mono"
                  />
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block font-semibold text-zinc-700 mb-1">Thickness (mm)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={specThickness}
                    onChange={(e) => setSpecThickness(e.target.value)}
                    className="w-full px-3 py-1.5 border border-zinc-200 rounded-lg"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-zinc-700 mb-1">Diameter (mm)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={specDiameter}
                    onChange={(e) => setSpecDiameter(e.target.value)}
                    className="w-full px-3 py-1.5 border border-zinc-200 rounded-lg"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-zinc-700 mb-1">Length (mm)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={specLength}
                    onChange={(e) => setSpecLength(e.target.value)}
                    className="w-full px-3 py-1.5 border border-zinc-200 rounded-lg"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-3 border-t border-zinc-100">
                <button
                  type="button"
                  onClick={() => setIsSpecModalOpen(false)}
                  className="px-3 py-1.5 border border-zinc-200 rounded-lg text-zinc-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 bg-zinc-900 text-white font-semibold rounded-lg hover:bg-zinc-800"
                >
                  Save Specification
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Universal Restock / Top-Up Modal */}
      {isRestockModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs">
          <div className="bg-white border border-zinc-200 rounded-2xl w-full max-w-lg p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-zinc-100 pb-3">
              <div>
                <h3 className="font-bold text-sm text-zinc-900 flex items-center gap-1.5">
                  <PackagePlus className="w-4 h-4 text-emerald-600" />
                  Restock Material Stock
                </h3>
                <p className="text-xs text-zinc-500">
                  {restockMaterial ? `${restockMaterial.materialCode} — ${restockMaterial.name}` : 'Select material to restock'}
                </p>
              </div>
              <button onClick={() => setIsRestockModalOpen(false)} className="text-zinc-400 hover:text-zinc-700">✕</button>
            </div>

            {/* Restock Mode Toggle: Top Up Existing Lot vs Receive New Batch */}
            <div className="grid grid-cols-2 gap-2 bg-zinc-100 p-1 rounded-xl">
              <button
                type="button"
                onClick={() => setRestockMode('TOP_UP')}
                className={`py-1.5 text-xs font-semibold rounded-lg transition-all ${
                  restockMode === 'TOP_UP' ? 'bg-white text-zinc-900 shadow-2xs font-bold' : 'text-zinc-600 hover:text-zinc-900'
                }`}
              >
                Top-Up Existing Lot / Batch
              </button>
              <button
                type="button"
                onClick={() => setRestockMode('NEW_BATCH')}
                className={`py-1.5 text-xs font-semibold rounded-lg transition-all ${
                  restockMode === 'NEW_BATCH' ? 'bg-white text-zinc-900 shadow-2xs font-bold' : 'text-zinc-600 hover:text-zinc-900'
                }`}
              >
                Receive Brand New Batch / Lot
              </button>
            </div>

            <form onSubmit={handleSubmitRestock} className="space-y-3.5 text-xs">
              {/* Material Selector if not preselected */}
              <div>
                <label className="block font-semibold text-zinc-700 mb-1">Target Material</label>
                <select
                  value={restockMaterial ? (restockMaterial.id || restockMaterial._id) : ''}
                  onChange={(e) => {
                    const selectedMat = materials.find(m => (m.id || m._id) === e.target.value) || null;
                    setRestockMaterial(selectedMat);
                    const matLots = lots.filter(l => l.materialId === e.target.value);
                    if (matLots.length > 0) {
                      setRestockLot(matLots[0]);
                    } else {
                      setRestockLot(null);
                      setRestockMode('NEW_BATCH');
                    }
                    if (selectedMat?.unitCost) setRestockUnitCost(String(selectedMat.unitCost));
                  }}
                  className="w-full px-3 py-1.5 border border-zinc-200 rounded-lg font-mono font-bold"
                >
                  {materials.map((m) => (
                    <option key={m.id || m._id} value={m.id || m._id}>
                      [{m.category || 'SHEET'}] {m.materialCode} — {m.name} (On-Hand: {m.quantityOnHand ?? 0} {m.unit})
                    </option>
                  ))}
                </select>
              </div>

              {/* Mode A: Select Existing Lot to Top Up */}
              {restockMode === 'TOP_UP' && (
                <div>
                  <label className="block font-semibold text-zinc-700 mb-1">Select Lot to Top Up</label>
                  {restockMaterial ? (
                    (() => {
                      const matLots = lots.filter(l => l.materialId === (restockMaterial.id || restockMaterial._id));
                      return matLots.length === 0 ? (
                        <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-800 text-xs">
                          No existing lots found for this material. Switching to <strong>New Batch</strong>.
                        </div>
                      ) : (
                        <select
                          value={restockLot ? (restockLot.id || restockLot._id) : ''}
                          onChange={(e) => {
                            const found = matLots.find(l => (l.id || l._id) === e.target.value) || null;
                            setRestockLot(found);
                            if (found?.unitCost) setRestockUnitCost(String(found.unitCost));
                            if (found?.supplier) setRestockSupplier(found.supplier);
                          }}
                          className="w-full px-3 py-1.5 border border-zinc-200 rounded-lg font-mono"
                        >
                          {matLots.map((l) => (
                            <option key={l.id || l._id} value={l.id || l._id}>
                              {l.lotNumber} | On-Hand: {l.quantityOnHand} {l.unit} | Status: {l.status} | Loc: {l.location}
                            </option>
                          ))}
                        </select>
                      );
                    })()
                  ) : null}
                </div>
              )}

              {/* Restock Quantity and Unit Cost */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-zinc-700 mb-1">
                    Quantity to Add ({restockMaterial?.unit || 'units'})
                  </label>
                  <input
                    type="number"
                    required
                    min="1"
                    step="any"
                    value={restockQty}
                    onChange={(e) => setRestockQty(Number(e.target.value))}
                    className="w-full px-3 py-1.5 border border-zinc-200 rounded-lg font-mono font-bold text-sm text-emerald-700"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-zinc-700 mb-1">Acquisition Unit Cost (₹)</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    placeholder="e.g. 500.00"
                    value={restockUnitCost}
                    onChange={(e) => setRestockUnitCost(e.target.value)}
                    className="w-full px-3 py-1.5 border border-zinc-200 rounded-lg font-mono"
                  />
                </div>
              </div>

              {/* Supplier & Notes */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-zinc-700 mb-1">Supplier / Vendor</label>
                  <input
                    type="text"
                    value={restockSupplier}
                    onChange={(e) => setRestockSupplier(e.target.value)}
                    placeholder="e.g. Apex Metals Ltd."
                    className="w-full px-3 py-1.5 border border-zinc-200 rounded-lg"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-zinc-700 mb-1">Audit Notes / Reason</label>
                  <input
                    type="text"
                    value={restockNotes}
                    onChange={(e) => setRestockNotes(e.target.value)}
                    placeholder="e.g. Scheduled PO Delivery"
                    className="w-full px-3 py-1.5 border border-zinc-200 rounded-lg"
                  />
                </div>
              </div>

              {/* Live Cost Computation Preview */}
              <div className="bg-emerald-50/70 border border-emerald-200 p-3 rounded-xl flex items-center justify-between font-mono">
                <div>
                  <span className="text-zinc-500 text-[10px] block font-sans">Total Restock Value:</span>
                  <span className="font-bold text-emerald-800 text-sm">
                    ₹{((Number(restockQty) || 0) * (Number(restockUnitCost) || 0)).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </span>
                </div>
                <div className="text-right">
                  <span className="text-zinc-500 text-[10px] block font-sans">Updated Physical Stock:</span>
                  <span className="font-bold text-zinc-900 text-sm">
                    {restockMode === 'TOP_UP' && restockLot 
                      ? `${(restockLot.quantityOnHand + Number(restockQty)).toFixed(2)} ${restockLot.unit}` 
                      : `${Number(restockQty)} ${restockMaterial?.unit || 'units'}`}
                  </span>
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-zinc-100">
                <button
                  type="button"
                  onClick={() => setIsRestockModalOpen(false)}
                  className="px-3 py-1.5 border border-zinc-200 rounded-lg text-zinc-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 bg-emerald-700 text-white font-semibold rounded-lg hover:bg-emerald-800 cursor-pointer shadow-2xs"
                >
                  Confirm Restock Receipt
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Receive New Lot from Scratch */}
      {isLotModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs">
          <div className="bg-white border border-zinc-200 rounded-2xl w-full max-w-md p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-zinc-100 pb-3">
              <h3 className="font-bold text-sm text-zinc-900">Receive Inventory Lot</h3>
              <button onClick={() => setIsLotModalOpen(false)} className="text-zinc-400 hover:text-zinc-700">✕</button>
            </div>
            <form onSubmit={handleCreateLot} className="space-y-3 text-xs">
              <div>
                <label className="block font-semibold text-zinc-700 mb-1">Lot Number</label>
                <input
                  type="text"
                  required
                  value={lotNumber}
                  onChange={(e) => setLotNumber(e.target.value.toUpperCase())}
                  className="w-full px-3 py-1.5 border border-zinc-200 rounded-lg font-mono font-bold"
                />
              </div>
              <div>
                <label className="block font-semibold text-zinc-700 mb-1">Material</label>
                <select
                  value={lotMatId}
                  onChange={(e) => {
                    setLotMatId(e.target.value);
                    const mat = materials.find(m => (m.id || m._id) === e.target.value);
                    if (mat?.specificationId) setLotSpecId(mat.specificationId);
                    if (mat?.unitCost) setLotUnitCost(String(mat.unitCost));
                  }}
                  className="w-full px-3 py-1.5 border border-zinc-200 rounded-lg font-mono"
                >
                  {materials.map((m) => (
                    <option key={m.id || m._id} value={m.id || m._id}>
                      [{m.category || 'SHEET'}] {m.materialCode} — {m.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-zinc-700 mb-1">Quantity Received</label>
                  <input
                    type="number"
                    required
                    min="1"
                    value={lotQty}
                    onChange={(e) => setLotQty(Number(e.target.value))}
                    className="w-full px-3 py-1.5 border border-zinc-200 rounded-lg font-mono font-bold text-emerald-700"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-zinc-700 mb-1">Storage Location</label>
                  <input
                    type="text"
                    required
                    value={lotLocation}
                    onChange={(e) => setLotLocation(e.target.value)}
                    className="w-full px-3 py-1.5 border border-zinc-200 rounded-lg font-mono"
                  />
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block font-semibold text-zinc-700 mb-1">Supplier</label>
                  <input
                    type="text"
                    value={lotSupplier}
                    onChange={(e) => setLotSupplier(e.target.value)}
                    className="w-full px-3 py-1.5 border border-zinc-200 rounded-lg"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-zinc-700 mb-1">Heat / Lot #</label>
                  <input
                    type="text"
                    value={lotHeat}
                    onChange={(e) => setLotHeat(e.target.value)}
                    className="w-full px-3 py-1.5 border border-zinc-200 rounded-lg font-mono"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-zinc-700 mb-1">Unit Cost (₹)</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    placeholder="500.00"
                    value={lotUnitCost}
                    onChange={(e) => setLotUnitCost(e.target.value)}
                    className="w-full px-3 py-1.5 border border-zinc-200 rounded-lg font-mono font-bold"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-3 border-t border-zinc-100">
                <button
                  type="button"
                  onClick={() => setIsLotModalOpen(false)}
                  className="px-3 py-1.5 border border-zinc-200 rounded-lg text-zinc-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 bg-zinc-900 text-white font-semibold rounded-lg hover:bg-zinc-800 cursor-pointer"
                >
                  Record Receipt
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Lot Cycle Count Adjustment */}
      {adjustLot && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs">
          <div className="bg-white border border-zinc-200 rounded-2xl w-full max-w-md p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-zinc-100 pb-3">
              <h3 className="font-bold text-sm text-zinc-900">Adjust Physical Stock ({adjustLot.lotNumber})</h3>
              <button onClick={() => setAdjustLot(null)} className="text-zinc-400 hover:text-zinc-700">✕</button>
            </div>
            <form onSubmit={handleAdjustLot} className="space-y-3 text-xs">
              <div>
                <label className="block font-semibold text-zinc-700 mb-1">New Physical On-Hand Quantity</label>
                <input
                  type="number"
                  required
                  min={adjustLot.quantityReserved}
                  value={adjustNewQty}
                  onChange={(e) => setAdjustNewQty(Number(e.target.value))}
                  className="w-full px-3 py-1.5 border border-zinc-200 rounded-lg font-mono font-bold text-sm"
                />
                <p className="text-[10px] text-zinc-400 mt-1 font-mono">Currently Reserved for WO: {adjustLot.quantityReserved} {adjustLot.unit}</p>
              </div>
              <div>
                <label className="block font-semibold text-zinc-700 mb-1">Reason / Justification</label>
                <input
                  type="text"
                  required
                  value={adjustReason}
                  onChange={(e) => setAdjustReason(e.target.value)}
                  className="w-full px-3 py-1.5 border border-zinc-200 rounded-lg"
                  placeholder="e.g. Physical inventory cycle count correction"
                />
              </div>
              <div className="flex justify-end gap-2 pt-3 border-t border-zinc-100">
                <button
                  type="button"
                  onClick={() => setAdjustLot(null)}
                  className="px-3 py-1.5 border border-zinc-200 rounded-lg text-zinc-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 bg-zinc-900 text-white font-semibold rounded-lg hover:bg-zinc-800 cursor-pointer"
                >
                  Confirm Adjustment
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
