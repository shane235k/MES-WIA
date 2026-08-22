import { useState, useEffect, useRef } from 'react';
import { 
  Sparkles, Send, X, ArrowRight, CheckCircle2, 
  HelpCircle, Box, RefreshCw 
} from 'lucide-react';
import { extractErrorMessage } from '../utils/apiError';

interface AIWorkOrderModalProps {
  isOpen: boolean;
  onClose: () => void;
  onApplyDraftToWizard: (draft: any) => void;
  onWorkOrderCreated: () => void;
}

interface Message {
  sender: 'USER' | 'AI';
  content: string;
  timestamp?: string;
  data?: any;
}

export default function AIWorkOrderModal({
  isOpen,
  onClose,
  onApplyDraftToWizard,
  onWorkOrderCreated
}: AIWorkOrderModalProps) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const [currentDraft, setCurrentDraft] = useState<any | null>(null);
  const [options, setOptions] = useState<Array<{ label: string; value: string; code?: string }>>([]);
  const [collectedFields, setCollectedFields] = useState<Record<string, any>>({});

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, options]);

  // Start new session on modal open
  useEffect(() => {
    if (isOpen) {
      startNewSession();
    } else {
      setSessionId(null);
      setMessages([]);
      setCurrentDraft(null);
      setOptions([]);
      setError(null);
    }
  }, [isOpen]);

  const startNewSession = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/ai/work-orders/session`, {
        method: 'POST'
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(extractErrorMessage(errData, 'Failed to initialize AI planning session'));
      }
      const data = await res.json();
      setSessionId(data.sessionId);
      setMessages(data.conversationHistory || [
        {
          sender: 'AI',
          content: data.message || 'Hello! What product would you like to manufacture, and how many units?'
        }
      ]);
    } catch (err: any) {
      setError(err.message || 'Error starting AI planning session');
    } finally {
      setLoading(false);
    }
  };

  const handleSendMessage = async (textToSend?: string) => {
    const text = (textToSend || inputMessage).trim();
    if (!text || !sessionId || loading) return;

    setInputMessage('');
    setError(null);

    // Optimistically push user message
    const userMsg: Message = {
      sender: 'USER',
      content: text,
      timestamp: new Date().toISOString()
    };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await fetch(`${API_URL}/api/ai/work-orders/session/${sessionId}/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text })
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(extractErrorMessage(errData, 'Failed to process message'));
      }

      const data = await res.json();

      const aiMsg: Message = {
        sender: 'AI',
        content: data.message,
        timestamp: new Date().toISOString(),
        data
      };
      setMessages(prev => [...prev, aiMsg]);
      setOptions(data.options || []);
      setCollectedFields(data.collectedFields || {});
      if (data.draft) {
        setCurrentDraft(data.draft);
      }
    } catch (err: any) {
      setError(err.message || 'Error processing AI response');
    } finally {
      setLoading(false);
    }
  };

  const handleDirectCreate = async () => {
    if (!currentDraft) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/ai/work-orders/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(currentDraft)
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(extractErrorMessage(errData, 'Failed to create Work Order from AI draft'));
      }

      onWorkOrderCreated();
      onClose();
    } catch (err: any) {
      setError(err.message || 'Error creating work order');
    } finally {
      setLoading(false);
    }
  };

  const handleReviewInWizard = () => {
    if (!currentDraft) return;
    onApplyDraftToWizard(currentDraft);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl h-[85vh] max-h-[780px] overflow-hidden border border-zinc-200 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200 bg-gradient-to-r from-zinc-900 via-zinc-800 to-zinc-900 text-white">
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-white/10 rounded-xl border border-white/20 shadow-2xs">
              <Sparkles className="w-5 h-5 text-amber-300 animate-pulse" />
            </div>
            <div>
              <h2 className="text-base font-bold flex items-center gap-2">
                AI Work Order Assistant
                <span className="text-[10px] font-mono font-bold bg-amber-400/20 text-amber-300 border border-amber-400/30 px-2 py-0.5 rounded-full">
                  Gemini Guided Planning
                </span>
              </h2>
              <p className="text-xs text-zinc-300">
                Conversational production order planning with automated BOM calculation and entity validation.
              </p>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            <button
              onClick={startNewSession}
              disabled={loading}
              className="p-1.5 rounded-lg text-zinc-300 hover:text-white hover:bg-white/10 cursor-pointer transition-colors"
              title="Reset conversation"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-zinc-300 hover:text-white hover:bg-white/10 cursor-pointer transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Main Content: Left Chat / Right Checklist & Live Draft */}
        <div className="flex-1 flex overflow-hidden">
          {/* Chat Column */}
          <div className="flex-1 flex flex-col bg-zinc-50/50 border-r border-zinc-200">
            {error && (
              <div className="p-3 m-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-700 flex items-center justify-between font-mono">
                <span>{error}</span>
                <button onClick={() => setError(null)} className="text-rose-500 hover:text-rose-700 cursor-pointer">
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            )}

            {/* Message Feed */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3.5">
              {messages.map((m, idx) => (
                <div
                  key={idx}
                  className={`flex ${m.sender === 'USER' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[85%] rounded-2xl p-3.5 text-xs shadow-2xs leading-relaxed ${
                      m.sender === 'USER'
                        ? 'bg-zinc-900 text-white rounded-br-xs font-medium'
                        : 'bg-white text-zinc-800 border border-zinc-200/90 rounded-bl-xs'
                    }`}
                  >
                    <div className="flex items-center gap-1.5 mb-1 text-[10px] font-bold uppercase tracking-wider opacity-70">
                      {m.sender === 'USER' ? (
                        <span>You</span>
                      ) : (
                        <span className="flex items-center gap-1 text-indigo-600">
                          <Sparkles className="w-3 h-3 text-amber-500" />
                          Planning Assistant
                        </span>
                      )}
                    </div>
                    <div className="whitespace-pre-wrap font-sans text-xs">
                      {m.content}
                    </div>
                  </div>
                </div>
              ))}

              {loading && (
                <div className="flex justify-start">
                  <div className="bg-white border border-zinc-200 rounded-2xl p-3 text-xs text-zinc-500 flex items-center gap-2 shadow-2xs font-mono">
                    <Sparkles className="w-3.5 h-3.5 text-amber-500 animate-spin" />
                    Planning requirements and validating MES entities...
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Interactive Quick Option Chips */}
            {options.length > 0 && (
              <div className="px-4 py-2 bg-white border-t border-zinc-200/80 flex flex-wrap gap-1.5 items-center">
                <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider block mr-1">
                  Suggestions:
                </span>
                {options.map((opt, i) => (
                  <button
                    key={i}
                    disabled={loading}
                    onClick={() => handleSendMessage(opt.code || opt.value || opt.label)}
                    className="px-2.5 py-1 bg-zinc-100 hover:bg-zinc-900 hover:text-white text-zinc-800 text-[11px] font-mono font-medium rounded-lg border border-zinc-200 transition-colors cursor-pointer shadow-2xs"
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            )}

            {/* Input Bar */}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSendMessage();
              }}
              className="p-3 bg-white border-t border-zinc-200 flex items-center gap-2"
            >
              <input
                type="text"
                disabled={loading}
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                placeholder="e.g. Manufacture 50 BRACKET-A units, priority high..."
                className="flex-1 px-3.5 py-2.5 bg-zinc-50 border border-zinc-200 rounded-xl text-xs focus:bg-white focus:outline-hidden focus:border-zinc-900 transition-all font-medium"
              />
              <button
                type="submit"
                disabled={loading || !inputMessage.trim()}
                className="p-2.5 bg-zinc-900 hover:bg-zinc-800 disabled:opacity-40 text-white rounded-xl cursor-pointer transition-colors shadow-2xs"
              >
                <Send className="w-4 h-4" />
              </button>
            </form>
          </div>

          {/* Right Column: Progressive Checklist & Live Draft */}
          <div className="w-80 bg-white flex flex-col p-4 space-y-4 overflow-y-auto">
            <div>
              <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider block mb-2">
                Requirements Checklist
              </span>
              <div className="space-y-1.5 font-mono text-xs">
                <div className={`p-2 rounded-lg border flex items-center justify-between ${
                  collectedFields.productId ? 'bg-emerald-50/70 border-emerald-200 text-emerald-900' : 'bg-zinc-50 border-zinc-200 text-zinc-500'
                }`}>
                  <span className="flex items-center gap-1.5">
                    {collectedFields.productId ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" /> : <HelpCircle className="w-3.5 h-3.5 text-zinc-400" />}
                    Product
                  </span>
                  <span className="font-bold text-[11px]">{collectedFields.productCode || 'Pending'}</span>
                </div>

                <div className={`p-2 rounded-lg border flex items-center justify-between ${
                  collectedFields.workflowId ? 'bg-emerald-50/70 border-emerald-200 text-emerald-900' : 'bg-zinc-50 border-zinc-200 text-zinc-500'
                }`}>
                  <span className="flex items-center gap-1.5">
                    {collectedFields.workflowId ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" /> : <HelpCircle className="w-3.5 h-3.5 text-zinc-400" />}
                    Workflow
                  </span>
                  <span className="font-bold text-[11px] truncate max-w-[120px]">{collectedFields.workflowCode || 'Pending'}</span>
                </div>

                <div className={`p-2 rounded-lg border flex items-center justify-between ${
                  collectedFields.quantity ? 'bg-emerald-50/70 border-emerald-200 text-emerald-900' : 'bg-zinc-50 border-zinc-200 text-zinc-500'
                }`}>
                  <span className="flex items-center gap-1.5">
                    {collectedFields.quantity ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" /> : <HelpCircle className="w-3.5 h-3.5 text-zinc-400" />}
                    Target Units
                  </span>
                  <span className="font-bold text-[11px]">{collectedFields.quantity ? `${collectedFields.quantity} u` : 'Pending'}</span>
                </div>

                <div className={`p-2 rounded-lg border flex items-center justify-between ${
                  collectedFields.supervisorId ? 'bg-emerald-50/70 border-emerald-200 text-emerald-900' : 'bg-zinc-50 border-zinc-200 text-zinc-500'
                }`}>
                  <span className="flex items-center gap-1.5">
                    {collectedFields.supervisorId ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" /> : <HelpCircle className="w-3.5 h-3.5 text-zinc-400" />}
                    Supervisor
                  </span>
                  <span className="font-bold text-[11px] truncate max-w-[120px]">{collectedFields.supervisorName || 'Pending'}</span>
                </div>
              </div>
            </div>

            {/* Live Draft Preview Card */}
            {currentDraft ? (
              <div className="p-3 bg-zinc-900 text-white rounded-xl space-y-3 shadow-md border border-zinc-800 text-xs">
                <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
                  <span className="font-bold text-[11px] uppercase tracking-wider text-amber-300 flex items-center gap-1">
                    <Sparkles className="w-3 h-3" />
                    Structured Draft Ready
                  </span>
                  <span className="text-[10px] font-mono bg-zinc-800 px-1.5 py-0.5 rounded text-zinc-300 font-bold">
                    {currentDraft.priority}
                  </span>
                </div>

                <div className="space-y-1 text-[11px] font-mono">
                  <div className="flex justify-between text-zinc-300">
                    <span>Batch Name:</span>
                    <strong className="text-white truncate max-w-[140px]">{currentDraft.name}</strong>
                  </div>
                  <div className="flex justify-between text-zinc-300">
                    <span>Target Output:</span>
                    <strong className="text-emerald-400">{currentDraft.quantity} units</strong>
                  </div>
                  <div className="flex justify-between text-zinc-300">
                    <span>Est. Material Cost:</span>
                    <strong className="text-emerald-400">₹{(currentDraft.totalEstimatedCost || 0).toLocaleString()}</strong>
                  </div>
                </div>

                {/* Material Breakdown */}
                {currentDraft.materialRequirements && currentDraft.materialRequirements.length > 0 && (
                  <div className="pt-1 border-t border-zinc-800 space-y-1">
                    <span className="text-[10px] uppercase tracking-wider text-zinc-400 font-bold block">
                      Required Materials
                    </span>
                    {currentDraft.materialRequirements.map((mat: any, mIdx: number) => (
                      <div key={mIdx} className="flex justify-between text-[10px] font-mono text-zinc-300 bg-zinc-800/80 px-2 py-1 rounded">
                        <span className="truncate max-w-[120px]">{mat.materialName}</span>
                        <span className="font-bold text-amber-300">{mat.totalRequiredQuantity} {mat.unit}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Draft Actions */}
                <div className="pt-2 space-y-2">
                  <button
                    onClick={handleReviewInWizard}
                    className="w-full py-2 bg-white hover:bg-zinc-100 text-zinc-900 rounded-lg text-xs font-bold transition-colors flex items-center justify-center gap-1.5 shadow-xs cursor-pointer"
                  >
                    <span>Review in Work Order Wizard</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>

                  <button
                    onClick={handleDirectCreate}
                    disabled={loading}
                    className="w-full py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-40 text-white rounded-lg text-xs font-bold transition-colors flex items-center justify-center gap-1.5 shadow-xs cursor-pointer"
                  >
                    <span>Create Work Order</span>
                  </button>
                </div>
              </div>
            ) : (
              <div className="p-4 bg-zinc-50 border border-dashed border-zinc-200 rounded-xl text-center text-xs text-zinc-400 space-y-1">
                <Box className="w-5 h-5 mx-auto text-zinc-300" />
                <p>Chat with the assistant to build your structured production draft.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
