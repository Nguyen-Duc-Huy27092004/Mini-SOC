import { useEffect, useState } from 'react';
import { 
  CheckCircle, Clock, AlertCircle, ShieldAlert,
  Activity, ArrowRight, ListTodo
} from 'lucide-react';
import { getTasks, updateTask } from '../api';
import type { ZabbixTaskOut } from '../types';

export function TaskCenter() {
  const [tasks, setTasks] = useState<ZabbixTaskOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState<string | null>(null);

  useEffect(() => {
    fetchTasks();
  }, []);

  const fetchTasks = async () => {
    try {
      const data = await getTasks();
      setTasks(data);
    } catch (err) {
      console.error('Failed to fetch tasks', err);
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateStatus = async (id: string, newStatus: string) => {
    setUpdating(id);
    try {
      await updateTask(id, { status: newStatus });
      await fetchTasks();
    } catch (err) {
      console.error('Failed to update task', err);
    } finally {
      setUpdating(null);
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority.toLowerCase()) {
      case 'critical': return 'text-rose-400 bg-rose-500/10 border-rose-500/20';
      case 'high': return 'text-amber-400 bg-amber-500/10 border-amber-500/20';
      case 'medium': return 'text-blue-400 bg-blue-500/10 border-blue-500/20';
      case 'low': return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20';
      default: return 'text-slate-400 bg-slate-500/10 border-slate-500/20';
    }
  };

  const getPriorityIcon = (priority: string) => {
    switch (priority.toLowerCase()) {
      case 'critical': return <ShieldAlert className="w-4 h-4" />;
      case 'high': return <AlertCircle className="w-4 h-4" />;
      case 'medium': return <Activity className="w-4 h-4" />;
      case 'low': return <CheckCircle className="w-4 h-4" />;
      default: return <Clock className="w-4 h-4" />;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-slate-400">
        <Activity className="w-6 h-6 animate-pulse mr-2" />
        Đang tải tác vụ đề xuất...
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <ListTodo className="w-5 h-5 text-indigo-400" />
            Trung tâm tác vụ
          </h1>
          <p className="text-xs text-slate-400 mt-1">Các tác vụ được đề xuất</p>
        </div>
        <div className="text-xs font-medium bg-indigo-500/10 text-indigo-400 px-3 py-1.5 rounded-lg border border-indigo-500/20">
          {tasks.length} Tác vụ đang hoạt động
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4">
        {tasks.length === 0 ? (
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-8 text-center">
            <CheckCircle className="w-12 h-12 text-emerald-500 mx-auto mb-3 opacity-50" />
            <h3 className="text-slate-200 font-medium"> Hoàn thành</h3>
            <p className="text-slate-400 text-sm mt-1">Không có tác vụ được đề xuất lúc này.</p>
          </div>
        ) : (
          tasks.map(task => (
            <div key={task.id} className="bg-slate-900/50 border border-slate-800 rounded-xl p-5 flex flex-col md:flex-row gap-5 items-start md:items-center transition-all hover:bg-slate-800/40">
              
              {/* Priority Badge */}
              <div className={`shrink-0 flex items-center justify-center w-12 h-12 rounded-xl border ${getPriorityColor(task.priority)}`}>
                {getPriorityIcon(task.priority)}
              </div>

              {/* Task Details */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="text-sm font-semibold text-slate-200 truncate">{task.task_type}</h3>
                  <span className="text-[10px] font-mono bg-slate-800 text-slate-400 px-2 py-0.5 rounded">
                    {task.hostname}
                  </span>
                </div>
                <p className="text-xs text-slate-400 leading-relaxed max-w-2xl">
                  {task.description}
                </p>
                <div className="flex items-center gap-4 mt-3 text-[10px] text-slate-500">
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {new Date(task.created_at).toLocaleDateString()}
                  </span>
                  {task.metric_value && (
                    <span className="flex items-center gap-1">
                      <Activity className="w-3 h-3" />
                      Giá trị: {task.metric_value.toFixed(1)}
                    </span>
                  )}
                  <span className="uppercase tracking-wider font-semibold opacity-70">
                    Nguồn: {task.source}
                  </span>
                </div>
              </div>

              {/* Actions */}
              <div className="shrink-0 flex items-center gap-2 w-full md:w-auto mt-4 md:mt-0 pt-4 md:pt-0 border-t md:border-t-0 border-slate-800">
                {task.status === 'Open' ? (
                  <button
                    onClick={() => handleUpdateStatus(task.id, 'In Progress')}
                    disabled={updating === task.id}
                    className="flex-1 md:flex-none px-4 py-2 bg-indigo-500 hover:bg-indigo-600 text-white text-xs font-medium rounded-lg transition flex items-center justify-center gap-2 disabled:opacity-50"
                  >
                    Bắt đầu <ArrowRight className="w-3 h-3" />
                  </button>
                ) : (
                  <button
                    onClick={() => handleUpdateStatus(task.id, 'Resolved')}
                    disabled={updating === task.id}
                    className="flex-1 md:flex-none px-4 py-2 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/20 text-xs font-medium rounded-lg transition flex items-center justify-center gap-2 disabled:opacity-50"
                  >
                    <CheckCircle className="w-3 h-3" /> Đã xử lý
                  </button>
                )}
                <button
                  onClick={() => handleUpdateStatus(task.id, 'Dismissed')}
                  disabled={updating === task.id}
                  className="px-3 py-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800 text-xs font-medium rounded-lg transition disabled:opacity-50"
                >
                  Từ chối
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
