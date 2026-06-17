import { useEffect, useState } from 'react';
import { 
  MailWarning, Send, Activity, AlertCircle, 
  CheckCircle, ServerOff, Server, Clock
} from 'lucide-react';
import { getNotifications, testNotification } from '../api';
import type { ZabbixNotificationOut } from '../types';

export function NotificationSettings() {
  const [logs, setLogs] = useState<ZabbixNotificationOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState(false);
  const [testEmail, setTestEmail] = useState('');
  const [testResult, setTestResult] = useState<{success: boolean, msg: string} | null>(null);

  useEffect(() => {
    fetchLogs();
  }, []);

  const fetchLogs = async () => {
    try {
      const data = await getNotifications(50);
      setLogs(data);
    } catch (err) {
      console.error('Failed to fetch notification logs', err);
    } finally {
      setLoading(false);
    }
  };

  const handleTestEmail = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!testEmail) return;
    
    setTesting(true);
    setTestResult(null);
    try {
      const res = await testNotification(testEmail);
      if (res.status === 'sent') {
        setTestResult({ success: true, msg: 'Test email sent successfully!' });
      } else {
        setTestResult({ success: false, msg: res.error_msg || 'Failed to send test email (check backend logs or SMTP config).' });
      }
      await fetchLogs();
    } catch (err: any) {
      setTestResult({ success: false, msg: err.message || 'Error triggering test.' });
    } finally {
      setTesting(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'sent': return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20';
      case 'failed': return 'text-rose-400 bg-rose-500/10 border-rose-500/20';
      case 'skipped': return 'text-amber-400 bg-amber-500/10 border-amber-500/20';
      default: return 'text-slate-400 bg-slate-500/10 border-slate-500/20';
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'server_down': return <ServerOff className="w-4 h-4 text-rose-400" />;
      case 'high_cpu':
      case 'high_disk': return <Activity className="w-4 h-4 text-amber-400" />;
      case 'test': return <Send className="w-4 h-4 text-indigo-400" />;
      default: return <AlertCircle className="w-4 h-4 text-slate-400" />;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-slate-400">
        <Activity className="w-6 h-6 animate-pulse mr-2" />
        Loading notification logs...
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <MailWarning className="w-5 h-5 text-indigo-400" />
            Notification Center
          </h1>
          <p className="text-xs text-slate-400 mt-1">Email alert logs and SMTP configuration testing</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Test Email Form */}
        <div className="lg:col-span-1">
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-5 sticky top-6">
            <h2 className="text-sm font-semibold text-slate-200 mb-4">Send Test Email</h2>
            <form onSubmit={handleTestEmail} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5">Recipient Address</label>
                <input 
                  type="email" 
                  value={testEmail}
                  onChange={e => setTestEmail(e.target.value)}
                  placeholder="admin@company.com"
                  required
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500 transition"
                />
              </div>
              <button 
                type="submit"
                disabled={testing || !testEmail}
                className="w-full py-2 bg-indigo-500 hover:bg-indigo-600 text-white text-sm font-medium rounded-lg transition flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {testing ? <Activity className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                {testing ? 'Sending...' : 'Send Test Alert'}
              </button>

              {testResult && (
                <div className={`p-3 rounded-lg border text-xs leading-relaxed ${
                  testResult.success 
                    ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' 
                    : 'bg-rose-500/10 border-rose-500/20 text-rose-400'
                }`}>
                  <div className="flex items-start gap-2">
                    {testResult.success ? <CheckCircle className="w-4 h-4 shrink-0" /> : <AlertCircle className="w-4 h-4 shrink-0" />}
                    <span>{testResult.msg}</span>
                  </div>
                </div>
              )}
            </form>

            <div className="mt-6 pt-6 border-t border-slate-800">
              <h3 className="text-xs font-semibold text-slate-400 mb-3 uppercase tracking-wider">Alert Thresholds</h3>
              <ul className="space-y-2 text-xs text-slate-300">
                <li className="flex justify-between"><span>CPU Usage:</span> <span className="font-mono text-amber-400">&gt; 90%</span></li>
                <li className="flex justify-between"><span>Disk Usage:</span> <span className="font-mono text-amber-400">&gt; 90%</span></li>
                <li className="flex justify-between"><span>Problem Severity:</span> <span className="font-mono text-rose-400">High / Disaster</span></li>
                <li className="flex justify-between"><span>Maintenance:</span> <span className="font-mono text-blue-400">&lt; 7 Days</span></li>
              </ul>
            </div>
          </div>
        </div>

        {/* Log History */}
        <div className="lg:col-span-2">
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-800 flex justify-between items-center bg-slate-900/80">
              <h2 className="text-sm font-semibold text-slate-200">Recent Dispatch Logs</h2>
              <span className="text-[10px] text-slate-500 uppercase tracking-wider">Last 50 entries</span>
            </div>
            
            <div className="divide-y divide-slate-800/50 max-h-[600px] overflow-y-auto">
              {logs.length === 0 ? (
                <div className="p-8 text-center text-slate-500 text-sm">
                  No notifications have been sent yet.
                </div>
              ) : (
                logs.map(log => (
                  <div key={log.id} className="p-4 hover:bg-slate-800/20 transition">
                    <div className="flex items-start gap-3">
                      <div className="mt-1 bg-slate-950 p-2 rounded-lg border border-slate-800 shrink-0">
                        {getTypeIcon(log.notification_type)}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <h3 className="text-sm font-medium text-slate-200 truncate" title={log.subject}>
                            {log.subject}
                          </h3>
                          <span className={`px-2 py-0.5 rounded text-[10px] font-semibold tracking-wider uppercase border shrink-0 ${getStatusColor(log.status)}`}>
                            {log.status}
                          </span>
                        </div>
                        <p className="text-xs text-slate-400 truncate mb-2">
                          To: {log.recipients || 'Unknown'}
                        </p>
                        
                        {log.status === 'failed' && log.error_msg && (
                          <div className="mb-2 p-2 rounded bg-rose-500/10 text-rose-400 text-[10px] font-mono whitespace-pre-wrap break-all">
                            {log.error_msg}
                          </div>
                        )}
                        
                        <div className="flex items-center gap-4 text-[10px] text-slate-500">
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {new Date(log.sent_at).toLocaleString()}
                          </span>
                          {log.hostname && (
                            <span className="flex items-center gap-1">
                              <Server className="w-3 h-3" />
                              {log.hostname}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
