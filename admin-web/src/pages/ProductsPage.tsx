import { useState, useEffect } from 'react';
import { Plus, Edit2, Trash2, X, BookOpen, GripVertical, Box, Layers, AlertCircle } from 'lucide-react';

interface RequiredMaterial {
  materialId: string;
  specificationId?: string;
  quantity: number;
  unit?: string;
}

interface RecipeStep {
  stepId: string;
  sequence: number;
  name: string;
  description?: string;
  requiredMachineType?: string;
  estimatedQuantityRate?: number;
  unit?: string;
  dependencies: string[];
  requiredMaterials?: RequiredMaterial[];
}

interface ProductRecipe {
  recipeId: string;
  recipeName: string;
  version: number;
  status: string;
  steps: RecipeStep[];
}

interface Product {
  id?: string;
  _id?: string;
  productCode: string;
  name: string;
  description: string;
  unit: string;
  active: boolean;
  recipes?: ProductRecipe[];
}

interface MaterialOption {
  id?: string;
  _id?: string;
  materialCode: string;
  name: string;
  unit: string;
  specificationId?: string;
}

interface SpecOption {
  id?: string;
  _id?: string;
  specificationCode: string;
  name: string;
  category: string;
  grade?: string;
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

export default function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [materials, setMaterials] = useState<MaterialOption[]>([]);
  const [specs, setSpecs] = useState<SpecOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);

  // Form states for Product
  const [productCode, setProductCode] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [unit, setUnit] = useState('pcs');
  const [active, setActive] = useState(true);

  // Recipe viewer/creator modal states
  const [selectedProductForRecipe, setSelectedProductForRecipe] = useState<Product | null>(null);
  const [isRecipeModalOpen, setIsRecipeModalOpen] = useState(false);
  const [recipeName, setRecipeName] = useState('');
  const [recipeVersion, setRecipeVersion] = useState(1);
  const [recipeSteps, setRecipeSteps] = useState<RecipeStep[]>([]);
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const [selectedRecipeIndex, setSelectedRecipeIndex] = useState<number>(-1);

  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  const fetchData = async () => {
    try {
      setLoading(true);
      const [prodRes, matRes, specRes] = await Promise.all([
        fetch(`${API_URL}/api/products`),
        fetch(`${API_URL}/api/materials`),
        fetch(`${API_URL}/api/materials/specifications`)
      ]);

      if (prodRes.ok) {
        const d = await prodRes.json();
        setProducts(Array.isArray(d) ? d : []);
      }
      if (matRes.ok) {
        const d = await matRes.json();
        setMaterials(Array.isArray(d) ? d : []);
      }
      if (specRes.ok) {
        const d = await specRes.json();
        setSpecs(Array.isArray(d) ? d : []);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load products');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const resetForm = () => {
    setProductCode('');
    setName('');
    setDescription('');
    setUnit('pcs');
    setActive(true);
    setEditingProduct(null);
  };

  const handleOpenCreate = () => {
    resetForm();
    setIsModalOpen(true);
  };

  const handleOpenEdit = (prod: Product) => {
    setEditingProduct(prod);
    setProductCode(prod.productCode);
    setName(prod.name);
    setDescription(prod.description);
    setUnit(prod.unit);
    setActive(prod.active);
    setIsModalOpen(true);
  };

  const loadSelectedRecipe = (prod: Product, index: number) => {
    setSelectedRecipeIndex(index);
    if (index === -1) {
      const nextVer = (prod.recipes?.length || 0) + 1;
      setRecipeVersion(nextVer);
      setRecipeName(`${prod.productCode}:v${nextVer}`);
      
      const existing = prod.recipes?.[prod.recipes.length - 1];
      if (existing && existing.steps && existing.steps.length > 0) {
        setRecipeSteps(JSON.parse(JSON.stringify(existing.steps)));
      } else {
        setRecipeSteps([
          { 
            stepId: 'STEP-10', 
            sequence: 10, 
            name: 'Laser Cutting', 
            requiredMachineType: 'CUTTING', 
            estimatedQuantityRate: 2.0, 
            dependencies: [],
            requiredMaterials: materials[0] ? [{
              materialId: materials[0].id || materials[0]._id || '',
              specificationId: materials[0].specificationId || undefined,
              quantity: 0.5,
              unit: materials[0].unit || 'sheets'
            }] : []
          },
          { 
            stepId: 'STEP-20', 
            sequence: 20, 
            name: 'Bending & Forming', 
            requiredMachineType: 'BENDING', 
            estimatedQuantityRate: 1.5, 
            dependencies: ['STEP-10'],
            requiredMaterials: []
          },
        ]);
      }
    } else {
      const existing = prod.recipes?.[index];
      if (existing) {
        setRecipeName(existing.recipeName);
        setRecipeVersion(existing.version || 1);
        
        const validStepIds = new Set(existing.steps?.map((s: any) => s.stepId) || []);
        const cleanedSteps = (existing.steps || []).map((s: any) => ({
          ...s,
          dependencies: (s.dependencies || []).filter((d: string) => validStepIds.has(d)),
          requiredMaterials: s.requiredMaterials || []
        }));
        
        setRecipeSteps(cleanedSteps);
      }
    }
  };

  const handleOpenCreateRecipe = (prod: Product) => {
    setSelectedProductForRecipe(prod);
    loadSelectedRecipe(prod, prod.recipes && prod.recipes.length > 0 ? 0 : -1);
    setIsRecipeModalOpen(true);
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

    const updated = [...recipeSteps];
    const [movedItem] = updated.splice(draggedIndex, 1);
    updated.splice(index, 0, movedItem);

    const resequenced = updated.map((step, idx) => ({
      ...step,
      sequence: (idx + 1) * 10
    }));

    setRecipeSteps(resequenced);
    setDraggedIndex(null);
  };

  const handleDragEnd = () => {
    setDraggedIndex(null);
  };

  const handleSaveRecipe = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedProductForRecipe) return;
    setError(null);

    // Validate material requirements
    for (const step of recipeSteps) {
      if (step.requiredMaterials) {
        for (const rm of step.requiredMaterials) {
          if (!rm.materialId) {
            setError(`Step ${step.stepId}: Please select a material for all requirement rows.`);
            return;
          }
          if (!rm.quantity || rm.quantity <= 0) {
            setError(`Step ${step.stepId}: Material quantity must be greater than 0.`);
            return;
          }
        }
      }
    }

    const payloadRecipe = {
      recipeId: `RECIPE-${selectedProductForRecipe.productCode}-V${recipeVersion}`,
      recipeName,
      version: recipeVersion,
      status: 'ACTIVE',
      steps: recipeSteps.map((s, idx) => ({
        stepId: s.stepId,
        sequence: (idx + 1) * 10,
        name: s.name,
        description: s.description || '',
        requiredCapabilityIds: [],
        requiredMachineType: s.requiredMachineType || 'CUTTING',
        estimatedQuantityRate: Number(s.estimatedQuantityRate || 1.0),
        unit: s.unit || selectedProductForRecipe.unit,
        dependencies: s.dependencies,
        requiredMaterials: (s.requiredMaterials || []).map(rm => ({
          materialId: rm.materialId,
          specificationId: rm.specificationId || undefined,
          quantity: Number(rm.quantity),
          unit: rm.unit || 'units'
        })),
        quantityRules: {}
      }))
    };

    try {
      const prodId = selectedProductForRecipe.id || selectedProductForRecipe._id;
      const res = await fetch(`${API_URL}/api/products/${prodId}/recipes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payloadRecipe)
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Failed to save recipe');
      }

      await fetchData();
      setIsRecipeModalOpen(false);
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleProductSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const payload = {
      productCode,
      name,
      description,
      unit,
      active,
    };

    try {
      const url = editingProduct
        ? `${API_URL}/api/products/${editingProduct.id || editingProduct._id}`
        : `${API_URL}/api/products`;
      const method = editingProduct ? 'PUT' : 'POST';

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
      resetForm();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm('Are you sure you want to delete this product?')) return;

    try {
      const response = await fetch(`${API_URL}/api/products/${id}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || 'Failed to delete product');
      }

      await fetchData();
    } catch (err: any) {
      setError(err.message);
    }
  };

  // Compute Recipe Total BOM summary
  const getRecipeBOMSummary = () => {
    const bomMap: Record<string, { materialName: string; specName?: string; totalQuantity: number; unit: string }> = {};
    for (const step of recipeSteps) {
      for (const rm of (step.requiredMaterials || [])) {
        if (!rm.materialId) continue;
        const mat = materials.find(m => (m.id || m._id) === rm.materialId);
        const spec = specs.find(s => (s.id || s._id) === rm.specificationId);
        const key = `${rm.materialId}_${rm.specificationId || 'none'}`;
        if (!bomMap[key]) {
          bomMap[key] = {
            materialName: mat?.name || rm.materialId,
            specName: spec?.name,
            totalQuantity: 0,
            unit: rm.unit || mat?.unit || 'units'
          };
        }
        bomMap[key].totalQuantity += Number(rm.quantity || 0);
      }
    }
    return Object.values(bomMap);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-900 flex items-center gap-2">
            <Box className="w-6 h-6 text-zinc-900" />
            Products & Recipe BOM Catalog
          </h1>
          <p className="text-xs text-zinc-500 mt-1">
            Define canonical manufacturing routing sequences, bill of materials (BOM), and machine constraints.
          </p>
        </div>
        <button
          onClick={handleOpenCreate}
          className="inline-flex items-center justify-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold text-white bg-zinc-900 rounded-lg hover:bg-zinc-800 transition-colors shadow-2xs cursor-pointer"
        >
          <Plus className="w-3.5 h-3.5" />
          Add Product
        </button>
      </div>

      {error && (
        <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-700 flex items-center justify-between font-mono">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-rose-500 hover:text-rose-700 text-xs">✕</button>
        </div>
      )}

      {/* Grid of Products */}
      {loading ? (
        <div className="flex items-center justify-center p-12 text-zinc-500 text-xs font-mono">
          Loading catalog...
        </div>
      ) : products.length === 0 ? (
        <div className="p-8 border border-dashed border-zinc-200 rounded-xl text-center text-zinc-500 text-xs">
          No products created yet.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {products.map((prod) => {
            const pId = prod.id || prod._id || '';
            const recipes = prod.recipes || [];
            return (
              <div
                key={pId}
                className="bg-white border border-zinc-200 rounded-2xl p-4 shadow-2xs flex flex-col justify-between hover:shadow-md transition-all"
              >
                <div>
                  <div className="flex items-start justify-between">
                    <div>
                      <span className="font-mono text-xs font-bold text-zinc-900 bg-zinc-100 px-2 py-0.5 rounded border border-zinc-200">
                        {prod.productCode}
                      </span>
                      <h3 className="font-bold text-zinc-900 text-sm mt-1.5">{prod.name}</h3>
                    </div>
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold ${
                        prod.active ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-zinc-100 text-zinc-600'
                      }`}
                    >
                      {prod.active ? 'ACTIVE' : 'INACTIVE'}
                    </span>
                  </div>

                  <p className="text-xs text-zinc-500 mt-2 line-clamp-2">{prod.description}</p>

                  <div className="space-y-1 text-xs text-zinc-600 my-3">
                    <div className="flex justify-between">
                      <span className="text-zinc-400">Unit of Output:</span>
                      <span className="font-mono text-zinc-800 font-semibold">{prod.unit}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-zinc-400">Recipes ({recipes.length}):</span>
                      <button
                        onClick={() => handleOpenCreateRecipe(prod)}
                        className="inline-flex items-center gap-1 text-[11px] font-semibold text-zinc-900 hover:underline cursor-pointer"
                      >
                        <Plus className="w-3 h-3" />
                        Configure Recipe
                      </button>
                    </div>
                  </div>

                  {/* Recipe Badges */}
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {recipes.map((r, rIdx) => (
                      <span
                        key={r.recipeId || rIdx}
                        className="inline-flex items-center gap-1 px-2 py-0.5 bg-zinc-50 border border-zinc-200 rounded text-[10px] font-mono text-zinc-700 font-medium"
                      >
                        <BookOpen className="w-2.5 h-2.5 text-zinc-400" />
                        {r.recipeName} ({r.steps?.length || 0} steps)
                      </span>
                    ))}
                  </div>
                </div>

                <div className="flex items-center justify-between gap-2 mt-4 pt-3 border-t border-zinc-100">
                  <button
                    onClick={() => handleOpenCreateRecipe(prod)}
                    className="inline-flex items-center gap-1 text-xs font-semibold text-zinc-900 bg-zinc-100 hover:bg-zinc-200 px-2.5 py-1.5 rounded-lg transition-colors cursor-pointer"
                  >
                    <BookOpen className="w-3.5 h-3.5" />
                    Recipe & BOM
                  </button>

                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => handleOpenEdit(prod)}
                      className="p-1.5 text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100 rounded-md transition-colors cursor-pointer"
                      title="Edit Product"
                    >
                      <Edit2 className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => handleDelete(pId)}
                      className="p-1.5 text-zinc-400 hover:text-rose-600 hover:bg-rose-50 rounded-md transition-colors cursor-pointer"
                      title="Delete Product"
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

      {/* Modal: Create/Edit Recipe with BOM and Drag-Drop */}
      {isRecipeModalOpen && selectedProductForRecipe && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[92vh] overflow-hidden border border-zinc-200 flex flex-col">
            <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200 bg-zinc-50/50">
              <div>
                <h2 className="text-base font-bold text-zinc-900 flex items-center gap-2">
                  <BookOpen className="w-4 h-4 text-zinc-900" />
                  Recipe & Material BOM: {selectedProductForRecipe.name}
                </h2>
                <p className="text-xs text-zinc-500">
                  Define manufacturing process steps and required raw material quantities per finished unit.
                </p>
              </div>
              <button
                onClick={() => setIsRecipeModalOpen(false)}
                className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-600 hover:bg-zinc-100"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSaveRecipe} className="flex-1 overflow-y-auto p-6 space-y-4">
              {/* Recipe Selector & Meta */}
              {selectedProductForRecipe.recipes && selectedProductForRecipe.recipes.length > 0 && (
                <div className="flex items-center justify-between bg-zinc-50 p-2.5 rounded-xl border border-zinc-200">
                  <span className="text-xs font-semibold text-zinc-700">Select Version:</span>
                  <select
                    value={selectedRecipeIndex}
                    onChange={(e) => loadSelectedRecipe(selectedProductForRecipe, Number(e.target.value))}
                    className="px-2 py-1 bg-white border border-zinc-300 rounded-lg text-xs font-mono"
                  >
                    <option value={-1}>+ Create New Version</option>
                    {selectedProductForRecipe.recipes.map((r, idx) => (
                      <option key={r.recipeId || idx} value={idx}>
                        {r.recipeName} (v{r.version || 1})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="sm:col-span-2">
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">Recipe Name</label>
                  <input
                    type="text"
                    required
                    value={recipeName}
                    onChange={(e) => setRecipeName(e.target.value)}
                    className="w-full px-3 py-1.5 border border-zinc-300 rounded-lg text-xs font-medium"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">Version Number</label>
                  <input
                    type="number"
                    min="1"
                    required
                    value={recipeVersion}
                    onChange={(e) => setRecipeVersion(Number(e.target.value))}
                    className="w-full px-3 py-1.5 border border-zinc-300 rounded-lg text-xs font-mono"
                  />
                </div>
              </div>

              {/* Recipe BOM Consolidated Summary Card */}
              {getRecipeBOMSummary().length > 0 && (
                <div className="bg-zinc-900 text-white rounded-xl p-3.5 text-xs shadow-xs space-y-2">
                  <div className="flex items-center gap-2 font-bold tracking-wide text-zinc-200">
                    <Layers className="w-3.5 h-3.5 text-indigo-400" />
                    CONSOLIDATED RECIPE BILL OF MATERIALS (BOM)
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2 pt-1 font-mono">
                    {getRecipeBOMSummary().map((item, bIdx) => (
                      <div key={bIdx} className="bg-zinc-800/80 p-2 rounded-lg border border-zinc-700/80">
                        <div className="font-bold text-zinc-100 truncate">{item.materialName}</div>
                        {item.specName && <div className="text-[10px] text-zinc-400 truncate">{item.specName}</div>}
                        <div className="text-emerald-400 font-bold text-[11px] mt-1">
                          {item.totalQuantity} {item.unit} / {selectedProductForRecipe.unit}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Recipe Steps Header */}
              <div className="pt-2">
                <div className="flex items-center justify-between mb-2">
                  <label className="block text-xs font-bold text-zinc-900 uppercase tracking-wider">
                    Process Sequence Steps & Material Requirements ({recipeSteps.length})
                  </label>
                  <button
                    type="button"
                    onClick={() => {
                      const nextSeq = (recipeSteps.length + 1) * 10;
                      setRecipeSteps([
                        ...recipeSteps,
                        {
                          stepId: `STEP-${nextSeq}`,
                          sequence: nextSeq,
                          name: `Process Step ${nextSeq}`,
                          requiredMachineType: 'CUTTING',
                          estimatedQuantityRate: 1.0,
                          dependencies: recipeSteps.length > 0 ? [recipeSteps[recipeSteps.length - 1].stepId] : [],
                          requiredMaterials: []
                        }
                      ]);
                    }}
                    className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-semibold bg-zinc-900 text-white rounded-lg hover:bg-zinc-800 cursor-pointer"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    Add Step
                  </button>
                </div>

                {/* Draggable Step Rows */}
                <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
                  {recipeSteps.map((s, idx) => (
                    <div
                      key={s.stepId || idx}
                      draggable
                      onDragStart={(e) => handleDragStart(e, idx)}
                      onDragOver={(e) => handleDragOver(e, idx)}
                      onDrop={(e) => handleDrop(e, idx)}
                      onDragEnd={handleDragEnd}
                      className={`p-3.5 bg-zinc-50 rounded-xl border space-y-2.5 transition-all ${
                        draggedIndex === idx
                          ? 'opacity-50 border-zinc-400 bg-zinc-100 shadow-md'
                          : 'border-zinc-200 hover:border-zinc-300 hover:bg-zinc-50/80'
                      }`}
                    >
                      {/* Step Header Line */}
                      <div className="flex items-center gap-2">
                        <GripVertical className="w-4 h-4 text-zinc-400 cursor-grab active:cursor-grabbing flex-shrink-0" />
                        
                        <span className="w-16 px-2 py-1 bg-white border border-zinc-200 rounded font-mono text-xs font-bold text-zinc-700 text-center flex-shrink-0">
                          {s.stepId}
                        </span>

                        <input
                          type="text"
                          value={s.name}
                          onChange={(e) => {
                            const updated = [...recipeSteps];
                            updated[idx].name = e.target.value;
                            setRecipeSteps(updated);
                          }}
                          placeholder="Step Name"
                          className="flex-1 px-3 py-1.5 bg-white border border-zinc-300 rounded-lg text-xs font-medium"
                        />

                        <select
                          value={s.requiredMachineType || 'CUTTING'}
                          onChange={(e) => {
                            const updated = [...recipeSteps];
                            updated[idx].requiredMachineType = e.target.value;
                            setRecipeSteps(updated);
                          }}
                          className="px-2.5 py-1.5 bg-white border border-zinc-300 rounded-lg text-xs uppercase font-semibold"
                        >
                          {MACHINE_TYPES.map(mt => (
                            <option key={mt} value={mt}>{mt}</option>
                          ))}
                        </select>

                        <button
                          type="button"
                          onClick={() => {
                            const targetStepId = s.stepId;
                            const filtered = recipeSteps
                              .filter((_, i) => i !== idx)
                              .map(otherStep => ({
                                ...otherStep,
                                dependencies: otherStep.dependencies.filter(d => d !== targetStepId)
                              }));
                            setRecipeSteps(filtered);
                          }}
                          className="p-1 text-rose-500 hover:text-rose-700 text-xs flex-shrink-0 cursor-pointer"
                          title="Remove step"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>

                      {/* Required Materials / BOM Section for this step */}
                      <div className="pl-6 pt-1 space-y-2 border-t border-zinc-200/60">
                        <div className="flex items-center justify-between">
                          <div>
                            <span className="text-[11px] font-bold text-zinc-700 flex items-center gap-1.5">
                              <Box className="w-3 h-3 text-zinc-600" />
                              Material Consumption per Finished Product Unit
                            </span>
                            <p className="text-[10px] text-zinc-400 font-normal">
                              Amount consumed by this operation for one finished product.
                            </p>
                          </div>
                          <button
                            type="button"
                            onClick={() => {
                              const updated = [...recipeSteps];
                              if (!updated[idx].requiredMaterials) updated[idx].requiredMaterials = [];
                              const defMat = materials[0];
                              updated[idx].requiredMaterials!.push({
                                materialId: defMat ? (defMat.id || defMat._id || '') : '',
                                specificationId: defMat?.specificationId || undefined,
                                quantity: 1.0,
                                unit: defMat?.unit || 'sheets'
                              });
                              setRecipeSteps(updated);
                            }}
                            className="inline-flex items-center gap-1 text-[11px] font-semibold text-zinc-900 bg-white hover:bg-zinc-100 border border-zinc-200 px-2 py-0.5 rounded cursor-pointer"
                          >
                            <Plus className="w-3 h-3" />
                            Add Material
                          </button>
                        </div>

                        {/* Material Rows */}
                        {s.requiredMaterials && s.requiredMaterials.length > 0 ? (
                          <div className="space-y-1.5">
                            {s.requiredMaterials.map((rm, mIdx) => (
                              <div key={mIdx} className="flex items-center gap-2 bg-white p-2 rounded-lg border border-zinc-200 text-xs font-mono">
                                {/* Material Dropdown */}
                                <select
                                  value={rm.materialId}
                                  onChange={(e) => {
                                    const updated = [...recipeSteps];
                                    const selectedMat = materials.find(m => (m.id || m._id) === e.target.value);
                                    updated[idx].requiredMaterials![mIdx].materialId = e.target.value;
                                    if (selectedMat) {
                                      updated[idx].requiredMaterials![mIdx].unit = selectedMat.unit;
                                      if (selectedMat.specificationId) {
                                        updated[idx].requiredMaterials![mIdx].specificationId = selectedMat.specificationId;
                                      }
                                    }
                                    setRecipeSteps(updated);
                                  }}
                                  className="flex-1 px-2 py-1 bg-zinc-50 border border-zinc-200 rounded text-xs"
                                >
                                  <option value="">Select Material...</option>
                                  {materials.map(m => (
                                    <option key={m.id || m._id} value={m.id || m._id}>
                                      {m.materialCode} — {m.name}
                                    </option>
                                  ))}
                                </select>

                                {/* Specification Dropdown */}
                                <select
                                  value={rm.specificationId || ''}
                                  onChange={(e) => {
                                    const updated = [...recipeSteps];
                                    updated[idx].requiredMaterials![mIdx].specificationId = e.target.value || undefined;
                                    setRecipeSteps(updated);
                                  }}
                                  className="flex-1 px-2 py-1 bg-zinc-50 border border-zinc-200 rounded text-xs"
                                >
                                  <option value="">No Spec / Generic</option>
                                  {specs.map(sp => (
                                    <option key={sp.id || sp._id} value={sp.id || sp._id}>
                                      {sp.specificationCode} ({sp.grade || sp.category})
                                    </option>
                                  ))}
                                </select>

                                {/* Quantity per Unit */}
                                <div className="flex items-center gap-1">
                                  <input
                                    type="number"
                                    step="0.001"
                                    min="0.001"
                                    required
                                    value={rm.quantity}
                                    onChange={(e) => {
                                      const updated = [...recipeSteps];
                                      updated[idx].requiredMaterials![mIdx].quantity = parseFloat(e.target.value) || 0;
                                      setRecipeSteps(updated);
                                    }}
                                    className="w-20 px-2 py-1 bg-zinc-50 border border-zinc-200 rounded text-xs font-bold"
                                    placeholder="Qty/unit"
                                  />
                                  <span className="text-[10px] text-zinc-500">{rm.unit || 'units'}</span>
                                </div>

                                <button
                                  type="button"
                                  onClick={() => {
                                    const updated = [...recipeSteps];
                                    updated[idx].requiredMaterials = updated[idx].requiredMaterials!.filter((_, i) => i !== mIdx);
                                    setRecipeSteps(updated);
                                  }}
                                  className="p-1 text-zinc-400 hover:text-rose-600 cursor-pointer"
                                  title="Remove material"
                                >
                                  <X className="w-3.5 h-3.5" />
                                </button>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="text-[11px] text-zinc-400 italic">No raw materials required for this operation step.</p>
                        )}
                      </div>

                      {/* Dependencies selector */}
                      <div className="flex items-center gap-2 text-xs text-zinc-600 pl-6 pt-1">
                        <span className="text-[11px] font-semibold text-zinc-400">Depends on:</span>
                        {recipeSteps.filter((_, i) => i !== idx).map((other) => {
                          const isDep = s.dependencies.includes(other.stepId);
                          return (
                            <button
                              key={other.stepId}
                              type="button"
                              onClick={() => {
                                const updated = [...recipeSteps];
                                if (isDep) {
                                  updated[idx].dependencies = updated[idx].dependencies.filter(d => d !== other.stepId);
                                } else {
                                  updated[idx].dependencies = [...updated[idx].dependencies, other.stepId];
                                }
                                setRecipeSteps(updated);
                              }}
                              className={`px-2 py-0.5 rounded font-mono text-[11px] border transition-colors cursor-pointer ${
                                isDep ? 'bg-zinc-900 text-white border-zinc-900 font-semibold' : 'bg-white text-zinc-600 border-zinc-200 hover:bg-zinc-100'
                              }`}
                            >
                              {other.stepId}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Total Recipe Material Input per Finished Product Card */}
              {recipeSteps.some(s => s.requiredMaterials && s.requiredMaterials.length > 0) && (
                <div className="bg-emerald-50/70 border border-emerald-200 rounded-xl p-3.5 space-y-2">
                  <div className="flex items-center justify-between text-xs font-bold text-emerald-950">
                    <span className="flex items-center gap-1.5">
                      <Box className="w-4 h-4 text-emerald-700" />
                      TOTAL MATERIAL INPUT PER FINISHED PRODUCT
                    </span>
                    <span className="text-[10px] font-mono text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded font-bold">
                      Recipe BOM
                    </span>
                  </div>
                  <p className="text-[10px] text-emerald-700 leading-tight">
                    Total raw material consumed across all operations to manufacture 1 finished product. (Material requirements define input consumption and do not determine or multiply product yield).
                  </p>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 pt-1 font-mono text-xs">
                    {getRecipeBOMSummary().map((bom, bIdx) => (
                      <div key={bIdx} className="bg-white px-2.5 py-1.5 rounded-lg border border-emerald-200 shadow-2xs flex justify-between items-center">
                        <span className="text-zinc-800 font-bold truncate max-w-[110px]">{bom.materialName}</span>
                        <span className="text-emerald-700 font-bold">{bom.totalQuantity} {bom.unit} / unit</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex justify-end gap-3 pt-4 border-t border-zinc-100">
                <button
                  type="button"
                  onClick={() => setIsRecipeModalOpen(false)}
                  className="px-4 py-2 border border-zinc-200 text-xs font-medium rounded-lg text-zinc-700 hover:bg-zinc-50 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-zinc-900 text-xs font-semibold rounded-lg text-white hover:bg-zinc-800 shadow-sm cursor-pointer"
                >
                  Save Recipe Version
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Create/Edit Product */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden border border-zinc-200">
            <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200 bg-zinc-50/50">
              <h2 className="text-base font-bold text-zinc-900">
                {editingProduct ? 'Edit Product' : 'Create New Product'}
              </h2>
              <button onClick={() => setIsModalOpen(false)} className="text-zinc-400 hover:text-zinc-600">
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleProductSubmit} className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">Product Code</label>
                <input
                  type="text"
                  required
                  disabled={!!editingProduct}
                  value={productCode}
                  onChange={(e) => setProductCode(e.target.value.toUpperCase())}
                  placeholder="e.g. BRACKET-A"
                  className="w-full px-3 py-2 border border-zinc-300 rounded-lg text-xs font-mono uppercase"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">Product Name</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Industrial Mounting Bracket"
                  className="w-full px-3 py-2 border border-zinc-300 rounded-lg text-xs font-medium"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">Description</label>
                <textarea
                  required
                  rows={2}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Product description..."
                  className="w-full px-3 py-2 border border-zinc-300 rounded-lg text-xs font-medium"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">Output Unit</label>
                  <input
                    type="text"
                    required
                    value={unit}
                    onChange={(e) => setUnit(e.target.value)}
                    className="w-full px-3 py-2 border border-zinc-300 rounded-lg text-xs font-mono"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">Status</label>
                  <select
                    value={active ? 'true' : 'false'}
                    onChange={(e) => setActive(e.target.value === 'true')}
                    className="w-full px-3 py-2 border border-zinc-300 rounded-lg text-xs font-medium"
                  >
                    <option value="true">ACTIVE</option>
                    <option value="false">INACTIVE</option>
                  </select>
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-4 border-t border-zinc-100">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 border border-zinc-200 text-xs font-medium rounded-lg text-zinc-700 hover:bg-zinc-50 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-zinc-900 text-xs font-semibold rounded-lg text-white hover:bg-zinc-800 shadow-sm cursor-pointer"
                >
                  {editingProduct ? 'Save Changes' : 'Create Product'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
