import { useState, useEffect, useRef } from 'react';
import { 
  Send, Upload, FileText, Trash2, Brain, 
  CheckCircle, XCircle, Loader2, MessageSquare,
  FolderOpen, Settings, Sparkles
} from 'lucide-react';
import * as api from './api/client';

function App() {
  const [activeTab, setActiveTab] = useState('chat');
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [documents, setDocuments] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [health, setHealth] = useState(null);
  const chatEndRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    checkHealth();
    if (activeTab === 'documents') loadDocuments();
  }, [activeTab]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const checkHealth = async () => {
    try {
      const data = await api.checkHealth();
      setHealth(data);
    } catch (e) {
      setHealth({ status: 'error', error: e.message });
    }
  };

  const loadDocuments = async () => {
    try {
      const docs = await api.getDocuments();
      setDocuments(docs);
    } catch (e) {
      console.error('Failed to load documents:', e);
    }
  };

  const handleSend = async () => {
    if (!input.trim() || loading) return;
    
    const userMessage = { role: 'user', content: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response = await api.sendChatMessage(input);
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: response.response,
        sources: response.sources 
      }]);
    } catch (e) {
      setMessages(prev => [...prev, { 
        role: 'error', 
        content: `Error: ${e.message}` 
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    try {
      await api.uploadDocument(file);
      await loadDocuments();
    } catch (e) {
      alert(`Upload failed: ${e.message}`);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDelete = async (id) => {
    if (!confirm('Delete this document?')) return;
    try {
      await api.deleteDocument(id);
      await loadDocuments();
    } catch (e) {
      alert(`Delete failed: ${e.message}`);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {/* Header */}
      <header className="bg-slate-800/50 backdrop-blur-sm border-b border-slate-700">
        <div className="max-w-6xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl">
                <Brain className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-white">Knowledge Hub AI</h1>
                <p className="text-xs text-slate-400">Enterprise RAG System</p>
              </div>
            </div>
            
            {/* Health Status */}
            <div className="flex items-center gap-2">
              {health && (
                <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm ${
                  health.status === 'healthy' 
                    ? 'bg-green-500/20 text-green-400' 
                    : 'bg-yellow-500/20 text-yellow-400'
                }`}>
                  {health.status === 'healthy' ? (
                    <CheckCircle className="w-4 h-4" />
                  ) : (
                    <XCircle className="w-4 h-4" />
                  )}
                  <span className="capitalize">{health.status}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Navigation */}
      <nav className="bg-slate-800/30 border-b border-slate-700">
        <div className="max-w-6xl mx-auto px-4">
          <div className="flex gap-1">
            {[
              { id: 'chat', label: 'Chat', icon: MessageSquare },
              { id: 'documents', label: 'Documents', icon: FolderOpen },
              { id: 'status', label: 'System Status', icon: Settings },
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors ${
                  activeTab === tab.id
                    ? 'text-blue-400 border-b-2 border-blue-400'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <tab.icon className="w-4 h-4" />
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-6xl mx-auto px-4 py-6">
        {activeTab === 'chat' && (
          <div className="bg-slate-800/50 rounded-2xl border border-slate-700 overflow-hidden">
            {/* Chat Messages */}
            <div className="h-[500px] overflow-y-auto p-6 space-y-4 chat-container">
              {messages.length === 0 && (
                <div className="flex flex-col items-center justify-center h-full text-center">
                  <Sparkles className="w-12 h-12 text-blue-400 mb-4" />
                  <h2 className="text-xl font-semibold text-white mb-2">
                    Ask me anything!
                  </h2>
                  <p className="text-slate-400 max-w-md">
                    I can answer questions based on your uploaded documents using AI-powered retrieval.
                  </p>
                </div>
              )}
              
              {messages.map((msg, i) => (
                <div
                  key={i}
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                    msg.role === 'user'
                      ? 'bg-blue-600 text-white'
                      : msg.role === 'error'
                      ? 'bg-red-500/20 text-red-300 border border-red-500/30'
                      : 'bg-slate-700 text-slate-100'
                  }`}>
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                    {msg.sources && msg.sources.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-slate-600">
                        <p className="text-xs text-slate-400 mb-1">Sources:</p>
                        {msg.sources.map((src, j) => (
                          <p key={j} className="text-xs text-slate-300">
                            • {src.document_name} (relevance: {(src.similarity_score * 100).toFixed(0)}%)
                          </p>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              
              {loading && (
                <div className="flex justify-start">
                  <div className="bg-slate-700 rounded-2xl px-4 py-3">
                    <Loader2 className="w-5 h-5 text-blue-400 animate-spin" />
                  </div>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            {/* Input */}
            <div className="p-4 border-t border-slate-700">
              <div className="flex gap-3">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                  placeholder="Ask a question about your documents..."
                  className="flex-1 bg-slate-700 border border-slate-600 rounded-xl px-4 py-3 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <button
                  onClick={handleSend}
                  disabled={loading || !input.trim()}
                  className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 disabled:cursor-not-allowed rounded-xl text-white font-medium transition-colors flex items-center gap-2"
                >
                  <Send className="w-4 h-4" />
                  Send
                </button>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'documents' && (
          <div className="space-y-6">
            {/* Upload Section */}
            <div className="bg-slate-800/50 rounded-2xl border border-slate-700 p-6">
              <h2 className="text-lg font-semibold text-white mb-4">Upload Documents</h2>
              <div className="border-2 border-dashed border-slate-600 rounded-xl p-8 text-center">
                <Upload className="w-10 h-10 text-slate-400 mx-auto mb-3" />
                <p className="text-slate-300 mb-2">Upload PDF, Markdown, or Text files</p>
                <p className="text-sm text-slate-500 mb-4">Files will be processed and indexed for AI search</p>
                <input
                  ref={fileInputRef}
                  type="file"
                  onChange={handleUpload}
                  accept=".pdf,.md,.txt"
                  className="hidden"
                  id="file-upload"
                />
                <label
                  htmlFor="file-upload"
                  className={`inline-flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-700 rounded-xl text-white font-medium cursor-pointer transition-colors ${
                    uploading ? 'opacity-50 cursor-not-allowed' : ''
                  }`}
                >
                  {uploading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Uploading...
                    </>
                  ) : (
                    <>
                      <Upload className="w-4 h-4" />
                      Choose File
                    </>
                  )}
                </label>
              </div>
            </div>

            {/* Documents List */}
            <div className="bg-slate-800/50 rounded-2xl border border-slate-700 p-6">
              <h2 className="text-lg font-semibold text-white mb-4">
                Your Documents ({documents.length})
              </h2>
              {documents.length === 0 ? (
                <p className="text-slate-400 text-center py-8">
                  No documents uploaded yet. Upload some files to get started!
                </p>
              ) : (
                <div className="space-y-3">
                  {documents.map(doc => (
                    <div
                      key={doc.id}
                      className="flex items-center justify-between p-4 bg-slate-700/50 rounded-xl"
                    >
                      <div className="flex items-center gap-3">
                        <FileText className="w-5 h-5 text-blue-400" />
                        <div>
                          <p className="text-white font-medium">{doc.filename}</p>
                          <p className="text-sm text-slate-400">
                            {doc.chunk_count || 0} chunks • {doc.status}
                          </p>
                        </div>
                      </div>
                      <button
                        onClick={() => handleDelete(doc.id)}
                        className="p-2 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'status' && (
          <div className="bg-slate-800/50 rounded-2xl border border-slate-700 p-6">
            <h2 className="text-lg font-semibold text-white mb-6">System Status</h2>
            {health ? (
              <div className="grid gap-4 md:grid-cols-2">
                {[
                  { label: 'Overall Status', value: health.status, ok: health.status === 'healthy' },
                  { label: 'Database', value: health.database || 'unknown', ok: health.database === 'healthy' },
                  { label: 'AI (Ollama)', value: health.ollama || 'unknown', ok: health.ollama === 'healthy' },
                  { label: 'Environment', value: health.environment || 'unknown', ok: true },
                  { label: 'Version', value: health.version || 'unknown', ok: true },
                ].map(item => (
                  <div key={item.label} className="p-4 bg-slate-700/50 rounded-xl">
                    <p className="text-sm text-slate-400 mb-1">{item.label}</p>
                    <div className="flex items-center gap-2">
                      {item.ok ? (
                        <CheckCircle className="w-4 h-4 text-green-400" />
                      ) : (
                        <XCircle className="w-4 h-4 text-yellow-400" />
                      )}
                      <span className={`font-medium capitalize ${
                        item.ok ? 'text-green-400' : 'text-yellow-400'
                      }`}>
                        {item.value}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-6 h-6 text-blue-400 animate-spin" />
              </div>
            )}
            <button
              onClick={checkHealth}
              className="mt-6 px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-white text-sm transition-colors"
            >
              Refresh Status
            </button>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="fixed bottom-0 left-0 right-0 bg-slate-800/80 backdrop-blur-sm border-t border-slate-700 py-3">
        <div className="max-w-6xl mx-auto px-4 text-center text-sm text-slate-500">
          Enterprise RAG System • Kubernetes + AI Powered
        </div>
      </footer>
    </div>
  );
}

export default App;
