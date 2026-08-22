import { useState, useEffect } from 'react';
import { 
  X, ArrowRight, ArrowLeft, Check, Wand2, 
  AlertCircle, BookOpen, GitBranch, GripVertical, Box
} from 'lucide-react';
import { extractErrorMessage } from '../utils/apiError';

interface Product {
  id?: string;
  _id?: string;
  productCode: string;
  name: string;
  unit?: string;
  recipes?: any[];
}

interface MaterialInfo {
  id?: string;
  _id?: string;
  materialCode: string;
  name: string;
  unit: string;
}

interface SpecInfo {
  id?: string;
  _id?: string;
  specificationCode: string;
  name: string;
  category: string;
}

interface RequiredMaterial {
  materialId: string;
  specificationId?: string;
  quantity: number;
  unit?: string;
}

interface WizardOperation {
  operationId: string;
  name: string;
  sequence: number;
  description?: string;
  requiredMachineType?: string;
  estimatedDurationSeconds: number;
  dependencies: string[];
  requiredMaterials?: RequiredMaterial[];
}

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

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

export default function WorkflowWizardModal({ isOpen, onClose, onSuccess }: Props) {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reference data
  const [products, setProducts] = useState<Product[]>([]);
  const [materials, setMaterials] = useState<MaterialInfo[]>([]);
  const [specs, setSpecs] = useState<SpecInfo[]>([]);

  // Step 1: Basic Info
  const [selectedProductId, setSelectedProductId] = useState('');
  const [workflowCode, setWorkflowCode] = useState('');
  const [name, setName] = useState('');
  const [version, setVersion] = useState(1);
  const status = 'ACTIVE';

  // Step 2: Recipe & Operations
  const [selectedRecipeIndex, setSelectedRecipeIndex] = useState<number>(0);
  const [operations, setOperations] = useState<WizardOperation[]>([]);
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);

  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  const loadRecipeForProduct = (prod: Product, recipeIndex: number = 0) => {
    setSelectedRecipeIndex(recipeIndex);
    const selectedRecipe = prod.recipes?.[recipeIndex];
    if (selectedRecipe && selectedRecipe.steps && selectedRecipe.steps.length > 0) {
      const validOpIds = new Set(
        selectedRecipe.steps.map((s: any) =>
          s.stepId ? s.stepId.replace('STEP', 'OP') : `OP-${s.sequence}`
        )
      );

      const mappedOps: WizardOperation[] = selectedRecipe.steps.map((s: any) => {
        const opId = s.stepId ? s.stepId.replace('STEP', 'OP') : `OP-${s.sequence}`;
        const rawDeps = (s.dependencies || []).map((d: string) => d.replace('STEP', 'OP'));
        const cleanDeps = rawDeps.filter((d: string) => validOpIds.has(d));
        return {
          operationId: opId,
          name: s.name,
          sequence: s.sequence,
          requiredMachineType: s.requiredMachineType || 'CUTTING',
          estimatedDurationSeconds: 10,
          dependencies: cleanDeps,
          requiredMaterials: s.requiredMaterials || []
        };
      });

      setOperations(mappedOps);
    } else {
      const defaultOps: WizardOperation[] = [
        { 
          operationId: 'OP-10', 
          name: 'Laser Cutting', 
          sequence: 10, 
          requiredMachineType: 'CUTTING', 
          estimatedDurationSeconds: 10, 
          dependencies: [],
          requiredMaterials: materials[0] ? [{
            materialId: materials[0].id || materials[0]._id || '',
            quantity: 0.5,
            unit: materials[0].unit
          }] : []
        },
        { operationId: 'OP-20', name: 'Bending', sequence: 20, requiredMachineType: 'BENDING', estimatedDurationSeconds: 10, dependencies: ['OP-10'], requiredMaterials: [] },
        { operationId: 'OP-30', name: 'Assembly', sequence: 30, requiredMachineType: 'WELDING', estimatedDurationSeconds: 10, dependencies: ['OP-20'], requiredMaterials: [] }
      ];
      setOperations(defaultOps);
    }
  };

  useEffect(() => {
    if (!isOpen) return;

    const loadData = async () => {
      try {
        const [prodRes, matRes, specRes] = await Promise.all([
          fetch(`${API_URL}/api/products`),
          fetch(`${API_URL}/api/materials`),
          fetch(`${API_URL}/api/materials/specifications`)
        ]);

        const prods = prodRes.ok ? await prodRes.json() : [];
        const mats = matRes.ok ? await matRes.json() : [];
        const sps = specRes.ok ? await specRes.json() : [];

        const prodsArr = Array.isArray(prods) ? prods : [];
        const matsArr = Array.isArray(mats) ? mats : [];
        const spsArr = Array.isArray(sps) ? sps : [];

        setProducts(prodsArr);
        setMaterials(matsArr);
        setSpecs(spsArr);

        if (prodsArr.length > 0) {
          const firstP = prodsArr[0];
          const pId = (firstP.id || firstP._id) as string;
          setSelectedProductId(pId);
          setName(`${firstP.name} Assembly Workflow`);
          generateWorkflowCode(firstP.productCode);
          loadRecipeForProduct(firstP, 0);
        }
      } catch (err: any) {
        setError(err.message);
      }
    };

    loadData();
  }, [isOpen]);

  const generateWorkflowCode = async (prodCode: string) => {
    try {
      const res = await fetch(`${API_URL}/api/workflows`);
      if (res.ok) {
        const wfs = await res.json();
        const num = wfs.length + 1;
        setWorkflowCode(`WF-${prodCode.substring(0, 4)}-${String(num).padStart(3, '0')}`);
      } else {
        setWorkflowCode(`WF-${prodCode.substring(0, 4)}-001`);
      }
    } catch {
      setWorkflowCode(`WF-${prodCode.substring(0, 4)}-001`);
    }
  };

  const handleProductChange = (prodId: string) => {
    setSelectedProductId(prodId);
    const prod = products.find(p => (p.id || p._id) === prodId);
    if (prod) {
      setName(`${prod.name} Production Workflow`);
      generateWorkflowCode(prod.productCode);
      loadRecipeForProduct(prod, 0);
    }
  };

  const handleDragStart = (e: React.DragEvent, index: number) => {
    setDraggedIndex(index);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    if (draggedIndex === null || draggedIndex === index) return;
    e.dataTransfer.dropEffect = 'move';
  };

  const handleDrop = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    if (draggedIndex === null || draggedIndex === index) return;

    const updated = [...operations];
    const [movedItem] = updated.splice(draggedIndex, 1);
    updated.splice(index, 0, movedItem);

    const resequenced = updated.map((op, idx) => ({
      ...op,
      sequence: (idx + 1) * 10
    }));

    setOperations(resequenced);
    setDraggedIndex(null);
  };

  const handleSubmitWorkflow = async () => {
    setError(null);
    setLoading(true);

    try {
      const workflowPayload = {
        workflowCode,
        name,
        productId: selectedProductId,
        version,
        status,
        operations: operations.map(op => ({
          operationId: op.operationId,
          name: op.name,
          sequence: op.sequence,
          requiredMachineType: op.requiredMachineType || 'CUTTING',
          estimatedDurationSeconds: op.estimatedDurationSeconds || 10,
          dependencies: op.dependencies,
          requiredMaterials: op.requiredMaterials || []
        }))
      };

      const res = await fetch(`${API_URL}/api/workflows`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(workflowPayload)
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(extractErrorMessage(errData, 'Failed to create workflow'));
      }

      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err.message || 'An unexpected error occurred');
    } finally {
      setLoading(false);
    }
  };

  const currentProduct = products.find(p => (p.id || p._id) === selectedProductId);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[92vh] overflow-hidden border border-zinc-200 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200 bg-zinc-50/50">
          <div className="flex items-center gap-2">
            <Wand2 className="w-5 h-5 text-zinc-900" />
            <div>
              <h2 className="text-base font-bold text-zinc-900">Workflow Definition Wizard</h2>
              <p className="text-xs text-zinc-500">
                Step {step} of 3 — {step === 1 ? 'Product & Code' : step === 2 ? 'Routing & Inherited BOM' : 'Review & Deploy'}
              </p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-600 hover:bg-zinc-100">
            <X className="w-4 h-4" />
          </button>
        </div>

        {error && (
          <div className="mx-6 mt-4 p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-700 flex items-center justify-between font-mono">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
            <button onClick={() => setError(null)} className="text-rose-500 hover:text-rose-700 text-xs">✕</button>
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {/* STEP 1: Basic Info & Product */}
          {step === 1 && (
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">Target Product</label>
                <select
                  value={selectedProductId}
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

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">Workflow Code</label>
                  <input
                    type="text"
                    required
                    value={workflowCode}
                    onChange={(e) => setWorkflowCode(e.target.value.toUpperCase())}
                    className="w-full px-3 py-2 border border-zinc-300 rounded-lg text-xs font-mono uppercase"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">Version</label>
                  <input
                    type="number"
                    min="1"
                    required
                    value={version}
                    onChange={(e) => setVersion(Number(e.target.value))}
                    className="w-full px-3 py-2 border border-zinc-300 rounded-lg text-xs font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">Workflow Title</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full px-3 py-2 border border-zinc-300 rounded-lg text-xs font-medium"
                />
              </div>
            </div>
          )}

          {/* STEP 2: Recipe & Operations with Inherited Materials */}
          {step === 2 && (
            <div className="space-y-4">
              {currentProduct && currentProduct.recipes && currentProduct.recipes.length > 0 && (
                <div className="bg-zinc-50 p-3 rounded-xl border border-zinc-200 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-zinc-900 flex items-center gap-1.5">
                      <BookOpen className="w-3.5 h-3.5 text-zinc-700" />
                      Select Canonical Recipe:
                    </span>
                    <select
                      value={selectedRecipeIndex}
                      onChange={(e) => loadRecipeForProduct(currentProduct, Number(e.target.value))}
                      className="px-2.5 py-1 bg-white border border-zinc-300 rounded text-xs font-mono"
                    >
                      {currentProduct.recipes.map((r: any, idx: number) => (
                        <option key={r.recipeId || idx} value={idx}>
                          {r.recipeName} ({r.steps?.length || 0} steps)
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              )}

              <div className="flex items-center justify-between pt-1">
                <h3 className="text-xs font-semibold text-zinc-900 uppercase tracking-wider">
                  Operation Steps & Inherited BOM ({operations.length})
                </h3>
              </div>

              <div className="space-y-3 max-h-80 overflow-y-auto pr-1">
                {operations.map((op, idx) => (
                  <div
                    key={op.operationId || idx}
                    draggable
                    onDragStart={(e) => handleDragStart(e, idx)}
                    onDragOver={(e) => handleDragOver(e, idx)}
                    onDrop={(e) => handleDrop(e, idx)}
                    onDragEnd={() => setDraggedIndex(null)}
                    className="p-3.5 bg-zinc-50 rounded-xl border border-zinc-200/90 space-y-2"
                  >
                    <div className="flex items-center gap-2">
                      <GripVertical className="w-4 h-4 text-zinc-400 cursor-grab active:cursor-grabbing flex-shrink-0" />

                      <span className="w-14 px-2 py-1 bg-white border rounded font-mono text-xs font-bold text-zinc-700 text-center flex-shrink-0">
                        {op.operationId}
                      </span>
                      <input
                        type="text"
                        value={op.name}
                        onChange={(e) => {
                          const updated = [...operations];
                          updated[idx].name = e.target.value;
                          setOperations(updated);
                        }}
                        placeholder="Step Name"
                        className="flex-1 px-3 py-1.5 bg-white border border-zinc-300 rounded-lg text-xs font-medium"
                      />
                      <span className="px-2.5 py-1 bg-zinc-200/70 border border-zinc-300 rounded text-xs font-bold font-mono uppercase text-zinc-800">
                        {op.requiredMachineType || 'CUTTING'}
                      </span>
                    </div>

                    {/* Inherited Material Requirements Badge */}
                    <div className="pl-6 pt-1">
                      {op.requiredMaterials && op.requiredMaterials.length > 0 ? (
                        <div className="bg-white p-2.5 rounded-lg border border-zinc-200/90 space-y-1 font-mono text-[11px]">
                          <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-400 block mb-1 flex items-center gap-1">
                            <Box className="w-3 h-3 text-zinc-600" />
                            Inherited Material Requirements (Recipe BOM per Unit)
                          </span>
                          {op.requiredMaterials.map((rm, mIdx) => {
                            const mat = materials.find(m => (m.id || m._id) === rm.materialId);
                            const spec = specs.find(s => (s.id || s._id) === rm.specificationId);
                            return (
                              <div key={mIdx} className="flex items-center justify-between text-zinc-800 bg-zinc-50 px-2 py-1 rounded">
                                <span className="font-bold text-zinc-900">{mat?.name || rm.materialId}</span>
                                {spec && <span className="text-zinc-500 text-[10px]">({spec.specificationCode})</span>}
                                <span className="text-emerald-700 font-bold">{rm.quantity} {rm.unit || mat?.unit || 'units'} / product</span>
                              </div>
                            );
                          })}
                        </div>
                      ) : (
                        <span className="text-[10px] text-zinc-400 italic font-mono">Material-free operation (0 raw materials consumed).</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* STEP 3: Review & Deploy */}
          {step === 3 && (
            <div className="space-y-4">
              <div className="bg-zinc-50 p-4 rounded-xl border border-zinc-200 space-y-3">
                <div className="flex justify-between items-center text-xs">
                  <span className="text-zinc-500">Workflow Code:</span>
                  <span className="font-mono font-bold text-zinc-900">{workflowCode}</span>
                </div>
                <div className="flex justify-between items-center text-xs">
                  <span className="text-zinc-500">Workflow Name:</span>
                  <span className="font-semibold text-zinc-900">{name}</span>
                </div>
                <div className="flex justify-between items-center text-xs">
                  <span className="text-zinc-500">Target Product:</span>
                  <span className="font-semibold text-zinc-900">{currentProduct?.name} ({currentProduct?.productCode})</span>
                </div>
              </div>

              <div>
                <span className="text-xs font-semibold text-zinc-700 block mb-2">Configured Routing & Inherited Materials</span>
                <div className="space-y-2 max-h-56 overflow-y-auto">
                  {operations.map(op => (
                    <div key={op.operationId} className="p-3 bg-white border border-zinc-200 rounded-xl space-y-1.5 text-xs">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <GitBranch className="w-3.5 h-3.5 text-zinc-400" />
                          <span className="font-bold text-zinc-900">{op.operationId}</span>
                          <span className="text-zinc-700">{op.name}</span>
                        </div>
                        <span className="px-2 py-0.5 bg-zinc-100 border border-zinc-200 rounded font-mono text-[10px] uppercase font-bold text-zinc-600">
                          {op.requiredMachineType}
                        </span>
                      </div>
                      {op.requiredMaterials && op.requiredMaterials.length > 0 && (
                        <div className="text-[11px] font-mono text-emerald-700 bg-emerald-50/70 p-1.5 rounded">
                          {op.requiredMaterials.map((rm, i) => {
                            const mat = materials.find(m => (m.id || m._id) === rm.materialId);
                            return (
                              <span key={i} className="block">
                                • {mat?.name || rm.materialId}: <strong>{rm.quantity} {rm.unit || 'units'} / finished unit</strong>
                              </span>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-zinc-200 bg-zinc-50/50">
          {step > 1 ? (
            <button
              type="button"
              onClick={() => setStep((step - 1) as any)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-zinc-700 bg-white border border-zinc-300 rounded-lg hover:bg-zinc-50 cursor-pointer"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              Back
            </button>
          ) : <div />}

          {step < 3 ? (
            <button
              type="button"
              onClick={() => setStep((step + 1) as any)}
              className="inline-flex items-center gap-1.5 px-4 py-1.5 text-xs font-semibold text-white bg-zinc-900 rounded-lg hover:bg-zinc-800 cursor-pointer"
            >
              Next Step
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          ) : (
            <button
              type="button"
              disabled={loading}
              onClick={handleSubmitWorkflow}
              className="inline-flex items-center gap-1.5 px-5 py-2 text-xs font-semibold text-white bg-zinc-900 rounded-lg hover:bg-zinc-800 shadow-sm cursor-pointer disabled:opacity-50"
            >
              <Check className="w-4 h-4" />
              {loading ? 'Creating...' : 'Deploy Workflow'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
