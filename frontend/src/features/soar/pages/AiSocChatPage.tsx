import { useState, useRef, useEffect, useCallback } from 'react';
import {
  Bot, Send, User, Loader2, Sparkles, RefreshCw,
  Copy, CheckCheck, Shield, Zap, MessageSquare,
  ExternalLink, ChevronDown, PlusCircle, Brain
} from 'lucide-react';
import api from '../../../shared/api/client';

// ── Types ─────────────────────────────────────────────────────────────────────

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  actions_executed?: Array<{ action: string; result: string }>;
  simulation_mode?: boolean;
}

interface ChatSession {
  id: string;
  messages: ChatMessage[];
  simulation_mode?: boolean;
}

// ── Quick Prompts ──────────────────────────────────────────────────────────────

const QUICK_PROMPTS = [
  { emoji: '🛡️', text: 'Tình trạng DDoS hiện tại?', label: 'DDoS Status' },
  { emoji: '📋', text: 'Tạo playbook chống brute force SSH sau 5 lần thất bại', label: 'Gen Playbook' },
  { emoji: '🔍', text: 'Giải thích tấn công HTTP Flood là gì?', label: 'Explain Attack' },
  { emoji: '⬆️', text: 'Những alert critical nào cần xử lý ngay?', label: 'Critical Alerts' },
];

// ── Markdown-lite renderer ─────────────────────────────────────────────────────

function renderContent(text: string): React.ReactNode {
  // Bold: **text**
  // Code: `code`
  // Line breaks
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`|\n)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className="text-white font-semibold">{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code key={i} className="px-1.5 py-0.5 rounded bg-slate-700 text-cyan-300 text-[11px] font-mono">
          {part.slice(1, -1)}
        </code>
      );
    }
    if (part === '\n') return <br key={i} />;
    return <span key={i}>{part}</span>;
  });
}

// ── Message bubble ─────────────────────────────────────────────────────────────

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const [copied, setCopied] = useState(false);
  const isBot = msg.role === 'assistant';
  const time = new Date(msg.timestamp).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });

  const copyText = () => {
    navigator.clipboard.writeText(msg.content).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div className={`flex gap-3 ${isBot ? 'items-start' : 'items-start flex-row-reverse'} group`}>
      {/* Avatar */}
      <div className={`w-7 h-7 rounded-lg shrink-0 flex items-center justify-center mt-0.5 ${
        isBot ? 'bg-violet-500/20 border border-violet-500/30' : 'bg-cyan-500/20 border border-cyan-500/30'
      }`}>
        {isBot ? <Bot className="w-3.5 h-3.5 text-violet-400" /> : <User className="w-3.5 h-3.5 text-cyan-400" />}
      </div>

      {/* Content */}
      <div className={`flex flex-col gap-1 max-w-[82%] ${isBot ? '' : 'items-end'}`}>
        <div className={`px-3.5 py-2.5 rounded-2xl text-sm leading-relaxed ${
          isBot
            ? 'bg-slate-800/70 border border-slate-700/60 text-slate-200 rounded-tl-sm'
            : 'bg-violet-600/80 border border-violet-500/40 text-white rounded-tr-sm'
        }`}>
          {renderContent(msg.content)}

          {/* Executed actions */}
          {msg.actions_executed && msg.actions_executed.length > 0 && (
            <div className="mt-3 space-y-1.5 border-t border-slate-700/40 pt-2">
              <p className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold flex items-center gap-1">
                <Zap className="w-3 h-3 text-cyan-400" /> Hành động đã thực thi
              </p>
              {msg.actions_executed.map((act, i) => (
                <div key={i} className="flex items-center gap-2 text-[11px]">
                  <CheckCheck className="w-3 h-3 text-emerald-400 shrink-0" />
                  <span className="text-slate-300 font-mono">{act.action}</span>
                  <span className="text-slate-500">{act.result}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className={`flex items-center gap-2 px-1 ${isBot ? '' : 'flex-row-reverse'}`}>
          <span className="text-[10px] text-slate-600">{time}</span>
          {msg.simulation_mode && (
            <span className="text-[10px] px-1.5 rounded bg-slate-800 text-slate-500 border border-slate-700">SIM</span>
          )}
          {isBot && (
            <button
              type="button"
              onClick={copyText}
              className="opacity-0 group-hover:opacity-100 transition text-slate-600 hover:text-slate-300"
              title="Sao chép"
            >
              {copied ? <CheckCheck className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Typing indicator ───────────────────────────────────────────────────────────

function TypingIndicator() {
  return (
    <div className="flex gap-3 items-start">
      <div className="w-7 h-7 rounded-lg shrink-0 flex items-center justify-center mt-0.5 bg-violet-500/20 border border-violet-500/30">
        <Bot className="w-3.5 h-3.5 text-violet-400" />
      </div>
      <div className="px-4 py-3 rounded-2xl rounded-tl-sm bg-slate-800/70 border border-slate-700/60">
        <div className="flex gap-1.5 items-center">
          <span className="w-1.5 h-1.5 bg-violet-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
          <span className="w-1.5 h-1.5 bg-violet-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
          <span className="w-1.5 h-1.5 bg-violet-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
          <span className="text-[11px] text-slate-500 ml-1">AI đang phân tích…</span>
        </div>
      </div>
    </div>
  );
}

// ── Main Component ─────────────────────────────────────────────────────────────

export function AiSocChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [simulationMode, setSimulationMode] = useState<boolean | null>(null);
  const [aiStatus, setAiStatus] = useState<{ mode: string; gemini_configured: boolean } | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Fetch AI status on mount
  useEffect(() => {
    api.get('/ai/status').then(r => {
      setAiStatus(r.data);
      setSimulationMode(r.data.mode === 'simulation');
    }).catch(() => setSimulationMode(true));
  }, []);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const sendMessage = useCallback(async (text?: string) => {
    const msg = (text ?? input).trim();
    if (!msg || loading) return;

    const userMsg: ChatMessage = {
      role: 'user',
      content: msg,
      timestamp: new Date().toISOString(),
    };

    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await api.post('/ai/chat', {
        message: msg,
        session_id: sessionId,
      });

      const { reply, actions_executed, simulation_mode: simMode, session_id: newSid } = res.data;
      if (newSid && !sessionId) setSessionId(newSid);
      if (simMode !== undefined) setSimulationMode(simMode);

      const botMsg: ChatMessage = {
        role: 'assistant',
        content: reply,
        timestamp: new Date().toISOString(),
        actions_executed: actions_executed ?? [],
        simulation_mode: simMode,
      };
      setMessages(prev => [...prev, botMsg]);
    } catch (err: unknown) {
      const errMsg = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail ?? 'Lỗi kết nối đến AI service.';
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `⚠️ ${errMsg}`,
        timestamp: new Date().toISOString(),
      }]);
    } finally {
      setLoading(false);
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [input, loading, sessionId]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const clearChat = () => {
    setMessages([]);
    setSessionId(null);
    inputRef.current?.focus();
  };

  const isEmpty = messages.length === 0;

  return (
    <div className="flex flex-col h-[calc(100vh-theme(spacing.11)-theme(spacing.12))] -m-6 bg-slate-950">
      {/* ── Header ── */}
      <div className="shrink-0 border-b border-slate-800 px-6 py-3 flex items-center justify-between bg-slate-900/60">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-violet-500/15 border border-violet-500/30 flex items-center justify-center">
            <Brain className="w-5 h-5 text-violet-400" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-white flex items-center gap-2">
              AI SOC Assistant
              {simulationMode === true && (
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400 font-medium">
                  Simulation Mode
                </span>
              )}
              {simulationMode === false && (
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-medium flex items-center gap-1">
                  <Sparkles className="w-2.5 h-2.5" /> Live · Gemini AI
                </span>
              )}
            </h1>
            <p className="text-[11px] text-slate-500">
              {aiStatus?.gemini_configured
                ? `Được hỗ trợ bởi ${aiStatus.mode === 'live' ? 'Google Gemini' : 'Simulation Engine'}`
                : 'Cấu hình GEMINI_API_KEY để bật AI thực'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {messages.length > 0 && (
            <button
              type="button"
              onClick={clearChat}
              className="flex items-center gap-1.5 text-[11px] px-3 py-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 border border-slate-700/50 transition"
            >
              <PlusCircle className="w-3.5 h-3.5" /> Cuộc trò chuyện mới
            </button>
          )}
          <a
            href="/api/v1/ai/status"
            target="_blank"
            rel="noopener noreferrer"
            className="text-slate-500 hover:text-slate-300 transition"
            title="AI Status API"
          >
            <ExternalLink className="w-4 h-4" />
          </a>
        </div>
      </div>

      {/* ── Messages area ── */}
      <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
        {/* Welcome screen */}
        {isEmpty && (
          <div className="flex flex-col items-center justify-center h-full gap-8 text-center">
            <div className="space-y-3">
              <div className="mx-auto w-16 h-16 rounded-2xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center">
                <Brain className="w-8 h-8 text-violet-400" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-white">Xin chào, SOC Analyst!</h2>
                <p className="text-sm text-slate-400 mt-1 max-w-sm mx-auto">
                  Tôi là AI Assistant của Mini-SOC. Tôi có thể giúp bạn phân tích threats,<br />
                  tạo playbooks, và trả lời câu hỏi bảo mật.
                </p>
              </div>
            </div>

            {/* Quick prompts */}
            <div className="grid grid-cols-2 gap-3 w-full max-w-lg">
              {QUICK_PROMPTS.map((p) => (
                <button
                  key={p.label}
                  type="button"
                  onClick={() => sendMessage(p.text)}
                  className="flex items-start gap-3 p-3.5 rounded-xl bg-slate-900 border border-slate-800 hover:border-violet-500/30 hover:bg-slate-800/60 transition text-left group"
                >
                  <span className="text-xl shrink-0">{p.emoji}</span>
                  <div>
                    <p className="text-xs font-semibold text-slate-300 group-hover:text-white transition">{p.label}</p>
                    <p className="text-[11px] text-slate-500 mt-0.5 leading-snug">{p.text}</p>
                  </div>
                </button>
              ))}
            </div>

            {simulationMode && (
              <div className="max-w-sm px-4 py-3 rounded-xl bg-amber-500/5 border border-amber-500/20 text-[11px] text-amber-400/80">
                💡 Đang chạy ở chế độ mô phỏng. Thêm{' '}
                <code className="font-mono text-amber-300">GEMINI_API_KEY</code> vào .env để kích hoạt AI thực.
              </div>
            )}
          </div>
        )}

        {/* Chat messages */}
        {messages.map((msg, i) => (
          <MessageBubble key={i} msg={msg} />
        ))}

        {/* Typing indicator */}
        {loading && <TypingIndicator />}

        <div ref={bottomRef} />
      </div>

      {/* ── Input area ── */}
      <div className="shrink-0 border-t border-slate-800 px-6 py-4 bg-slate-900/40">
        {/* Context badges (could show linked alert/incident) */}
        <div className="flex items-end gap-3">
          <div className="flex-1 relative">
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Hỏi về threats, block IP, tạo playbook… (Enter để gửi, Shift+Enter xuống dòng)"
              rows={1}
              className="w-full bg-slate-800 border border-slate-700 text-slate-200 placeholder-slate-500 text-sm rounded-xl px-4 py-3 pr-12 resize-none focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/20 transition"
              style={{ maxHeight: '120px', overflowY: 'auto' }}
              onInput={(e) => {
                const el = e.currentTarget;
                el.style.height = 'auto';
                el.style.height = Math.min(el.scrollHeight, 120) + 'px';
              }}
            />
            <div className="absolute right-3 bottom-3 text-[10px] text-slate-600">
              {input.length > 0 && `${input.length}`}
            </div>
          </div>

          <button
            type="button"
            onClick={() => sendMessage()}
            disabled={!input.trim() || loading}
            className="shrink-0 w-10 h-10 rounded-xl bg-violet-600 hover:bg-violet-500 disabled:opacity-30 disabled:cursor-not-allowed flex items-center justify-center transition"
          >
            {loading
              ? <Loader2 className="w-4 h-4 text-white animate-spin" />
              : <Send className="w-4 h-4 text-white" />
            }
          </button>
        </div>

        <p className="mt-2 text-[10px] text-slate-600 text-center">
          AI có thể mắc sai sót. Hãy xác minh trước khi thực thi action trên production.
        </p>
      </div>
    </div>
  );
}
