import { useState, useEffect } from 'react';
import { AlertCircle, CheckCircle, Wand2, Eye, Trash2 } from 'lucide-react';
import WorkflowWizardModal from '../components/WorkflowWizardModal';

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
  supervisorId?: string;
  version: number;
  status: string;
  operations: any[];
}

interface WorkflowsPageProps {
  onSelectWorkflow: (wfId: string) => void;
}

export default function WorkflowsPage({ onSelectWorkflow }: WorkflowsPageProps) {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<string[] | null>(null);
  const [validationSuccess, setValidationSuccess] = useState<string | null>(null);
  const [isWizardOpen, setIsWizardOpen] = useState(false);

  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  const fetchData = async () => {
    try {
      const [wfRes, prodRes] = await Promise.all([
        fetch(`${API_URL}/api/workflows`),
        fetch(`${API_URL}/api/products`)
      ]);
      if (!wfRes.ok || !prodRes.ok) throw new Error('Failed to load workflows or products');
      
      const wfData = await wfRes.json();
      const prodData = await prodRes.json();
      
      setWorkflows(wfData);
      setProducts(prodData.filter((p: Product) => p.active));
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleValidate = async (wfId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setValidationErrors(null);
    setValidationSuccess(null);
    try {
      const res = await fetch(`${API_URL}/api/workflows/${wfId}/validate`, { method: 'POST' });
      const data = await res.json();
      if (data.valid) {
        setValidationSuccess('Workflow structure is fully validated: all DAG dependencies and resources are sound.');
      } else {
        setValidationErrors(data.errors);
      }
    } catch (err: any) {
      setValidationErrors([err.message]);
    }
  };

  const handleActivate = async (wfId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setValidationErrors(null);
    setValidationSuccess(null);
    try {
      const res = await fetch(`${API_URL}/api/workflows/${wfId}/activate`, { method: 'POST' });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Activation failed');
      }
      setValidationSuccess('Workflow activated successfully.');
      fetchData();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleDelete = async (id: string, name: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm(`Are you sure you want to delete workflow "${name}"?`)) return;
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/workflows/${id}`, {
        method: 'DELETE'
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Failed to delete workflow');
      }
      fetchData();
    } catch (err: any) {
      setError(err.message);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-900">Workflows & DAG Routing</h1>
          <p className="text-sm text-zinc-500">
            Design, validate, and manage executable production graphs and machine bindings.
          </p>
        </div>
        <button
          onClick={() => setIsWizardOpen(true)}
          className="inline-flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium text-white bg-zinc-900 rounded-lg hover:bg-zinc-800 transition-colors shadow-sm"
        >
          <Wand2 className="w-4 h-4 text-amber-400" />
          Workflow Wizard
        </button>
      </div>

      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-lg text-sm text-rose-700">
          {error}
        </div>
      )}

      {validationErrors && validationErrors.length > 0 && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-lg space-y-1">
          <div className="flex items-center gap-2 text-sm font-semibold text-rose-800">
            <AlertCircle className="w-4 h-4" />
            Validation Issues Detected:
          </div>
          <ul className="list-disc list-inside text-xs text-rose-700 pl-2">
            {validationErrors.map((err, idx) => (
              <li key={idx}>{err}</li>
            ))}
          </ul>
        </div>
      )}

      {validationSuccess && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-lg text-sm text-emerald-800 flex items-center gap-2">
          <CheckCircle className="w-4 h-4 text-emerald-600" />
          {validationSuccess}
        </div>
      )}

      {/* Grid of Workflows */}
      {loading ? (
        <div className="flex items-center justify-center p-12 text-zinc-500 text-sm">
          Loading workflows...
        </div>
      ) : workflows.length === 0 ? (
        <div className="p-8 border border-dashed border-zinc-300 rounded-xl text-center text-zinc-500 text-sm">
          No workflows found. Use the Workflow Wizard to create a new production routing graph.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {workflows.map((wf) => {
            const wfId = (wf.id || wf._id) as string;
            const product = products.find(p => (p.id || p._id) === wf.productId);
            const opsCount = wf.operations?.length || 0;

            return (
              <div
                key={wfId}
                onClick={() => onSelectWorkflow(wfId)}
                className="bg-white border border-zinc-200 rounded-xl p-5 shadow-xs hover:shadow-md hover:border-zinc-300 transition-all flex flex-col justify-between cursor-pointer group"
              >
                <div>
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div>
                      <span className="text-xs font-mono font-bold text-zinc-400 uppercase tracking-wider">
                        {wf.workflowCode}
                      </span>
                      <h3 className="font-semibold text-zinc-900 group-hover:text-zinc-700 text-base">
                        {wf.name}
                      </h3>
                    </div>
                    <span
                      className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${
                        wf.status === 'ACTIVE'
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                          : 'bg-zinc-100 text-zinc-600'
                      }`}
                    >
                      {wf.status}
                    </span>
                  </div>

                  <div className="space-y-1.5 text-xs text-zinc-500 my-3">
                    <div className="flex justify-between">
                      <span>Product:</span>
                      <span className="font-medium text-zinc-900 font-mono">
                        {product ? product.productCode : wf.productId}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>Version:</span>
                      <span className="font-medium text-zinc-900 font-mono">v{wf.version}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Operations:</span>
                      <span className="font-medium text-zinc-900">{opsCount} Steps</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-between gap-2 mt-4 pt-3 border-t border-zinc-100">
                  <div className="flex items-center gap-1.5">
                    <button
                      onClick={(e) => handleValidate(wfId, e)}
                      className="px-2.5 py-1 bg-zinc-100 hover:bg-zinc-200 text-zinc-700 rounded-md text-xs font-medium transition-colors"
                      title="Validate DAG Routing"
                    >
                      Validate
                    </button>
                    {wf.status !== 'ACTIVE' && (
                      <button
                        onClick={(e) => handleActivate(wfId, e)}
                        className="px-2.5 py-1 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 rounded-md text-xs font-medium transition-colors"
                        title="Activate Workflow"
                      >
                        Activate
                      </button>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={(e) => handleDelete(wfId, wf.name, e)}
                      className="p-1.5 text-zinc-400 hover:text-rose-600 hover:bg-rose-50 rounded-md transition-colors"
                      title="Delete Workflow"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => onSelectWorkflow(wfId)}
                      className="inline-flex items-center gap-1 text-xs font-semibold text-zinc-900 hover:text-zinc-600"
                    >
                      <Eye className="w-3.5 h-3.5" />
                      Open Designer
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Workflow Wizard Modal */}
      <WorkflowWizardModal
        isOpen={isWizardOpen}
        onClose={() => setIsWizardOpen(false)}
        onSuccess={() => {
          fetchData();
        }}
      />
    </div>
  );
}
