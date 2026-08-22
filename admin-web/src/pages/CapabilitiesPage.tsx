import { useState, useEffect } from 'react';
import { Plus, Edit2, Trash2, X } from 'lucide-react';

interface Capability {
  id?: string;
  _id?: string;
  code: string;
  name: string;
  description: string;
  createdAt?: string;
}

export default function CapabilitiesPage() {
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingCapability, setEditingCapability] = useState<Capability | null>(null);
  
  // Form state
  const [code, setCode] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  
  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  const fetchCapabilities = async () => {
    try {
      const response = await fetch(`${API_URL}/api/capabilities`);
      if (!response.ok) throw new Error('Failed to fetch capabilities');
      const data = await response.json();
      setCapabilities(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCapabilities();
  }, []);

  const resetForm = () => {
    setCode('');
    setName('');
    setDescription('');
    setEditingCapability(null);
  };

  const handleOpenCreate = () => {
    resetForm();
    setIsModalOpen(true);
  };

  const handleOpenEdit = (cap: Capability) => {
    setEditingCapability(cap);
    setCode(cap.code);
    setName(cap.name);
    setDescription(cap.description);
    setIsModalOpen(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const payload = { code, name, description };
    const method = editingCapability ? 'PUT' : 'POST';
    const url = editingCapability 
      ? `${API_URL}/api/capabilities/${editingCapability.id || editingCapability._id}`
      : `${API_URL}/api/capabilities`;

    try {
      const response = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || 'Save failed');
      }

      await fetchCapabilities();
      setIsModalOpen(false);
      resetForm();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleDelete = async (capId: string) => {
    if (!confirm('Are you sure you want to delete this capability?')) return;
    setError(null);
    try {
      const response = await fetch(`${API_URL}/api/capabilities/${capId}`, {
        method: 'DELETE',
      });
      if (!response.ok) throw new Error('Failed to delete capability');
      await fetchCapabilities();
    } catch (err: any) {
      setError(err.message);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-xl font-semibold text-neutral-900">Capabilities</h2>
          <p className="text-xs text-neutral-500 mt-0.5">Define operations or processes that can be executed in the factory.</p>
        </div>
        <button
          onClick={handleOpenCreate}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-white bg-black hover:bg-neutral-800 rounded transition-colors"
        >
          <Plus className="w-3.5 h-3.5" />
          Add Capability
        </button>
      </div>

      {error && (
        <div className="p-3 border border-red-200 bg-red-50/50 rounded text-xs text-red-600 font-mono">
          Error: {error}
        </div>
      )}

      {loading ? (
        <div className="text-center py-12 text-sm text-neutral-500 font-mono">Loading capabilities...</div>
      ) : capabilities.length === 0 ? (
        <div className="text-center py-12 border border-dashed border-neutral-200 rounded-lg bg-white">
          <p className="text-sm text-neutral-500">No capabilities found.</p>
        </div>
      ) : (
        <div className="border border-neutral-200 rounded-lg bg-white overflow-hidden">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-neutral-50 border-b border-neutral-200 text-neutral-500 font-mono">
                <th className="p-4 font-medium">Code</th>
                <th className="p-4 font-medium">Name</th>
                <th className="p-4 font-medium">Description</th>
                <th className="p-4 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {capabilities.map((cap) => {
                const id = cap.id || cap._id || '';
                return (
                  <tr key={id} className="hover:bg-neutral-50/50 transition-colors">
                    <td className="p-4 font-mono font-medium text-neutral-900">{cap.code}</td>
                    <td className="p-4 text-neutral-900">{cap.name}</td>
                    <td className="p-4 text-neutral-500 max-w-xs truncate">{cap.description}</td>
                    <td className="p-4 text-right space-x-2">
                      <button
                        onClick={() => handleOpenEdit(cap)}
                        className="inline-flex p-1 hover:bg-neutral-100 rounded text-neutral-500 hover:text-neutral-900 transition-colors"
                        title="Edit"
                      >
                        <Edit2 className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => handleDelete(id)}
                        className="inline-flex p-1 hover:bg-neutral-100 rounded text-neutral-500 hover:text-red-600 transition-colors"
                        title="Delete"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/10 backdrop-blur-xs">
          <div className="bg-white border border-neutral-200 rounded-lg shadow-lg w-full max-w-md p-6 relative">
            <button
              onClick={() => setIsModalOpen(false)}
              className="absolute top-4 right-4 p-1 hover:bg-neutral-100 rounded text-neutral-400 hover:text-neutral-900"
            >
              <X className="w-4 h-4" />
            </button>
            <h3 className="text-sm font-semibold text-neutral-900 mb-4">
              {editingCapability ? 'Edit Capability' : 'Create Capability'}
            </h3>
            
            <form onSubmit={handleSubmit} className="space-y-4 text-xs">
              <div>
                <label className="block font-medium text-neutral-700 mb-1">Capability Code</label>
                <input
                  type="text"
                  required
                  disabled={!!editingCapability}
                  value={code}
                  onChange={(e) => setCode(e.target.value.toUpperCase())}
                  placeholder="e.g. CNC_MILLING"
                  className="w-full px-3 py-2 border border-neutral-200 rounded outline-hidden focus:border-black font-mono disabled:bg-neutral-50 disabled:text-neutral-400"
                />
              </div>
              
              <div>
                <label className="block font-medium text-neutral-700 mb-1">Name</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. CNC Milling"
                  className="w-full px-3 py-2 border border-neutral-200 rounded outline-hidden focus:border-black"
                />
              </div>

              <div>
                <label className="block font-medium text-neutral-700 mb-1">Description</label>
                <textarea
                  required
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Describe the capability..."
                  rows={3}
                  className="w-full px-3 py-2 border border-neutral-200 rounded outline-hidden focus:border-black resize-none"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-3 py-1.5 border border-neutral-200 rounded hover:bg-neutral-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3 py-1.5 bg-black hover:bg-neutral-800 text-white rounded transition-colors font-medium"
                >
                  Save
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
