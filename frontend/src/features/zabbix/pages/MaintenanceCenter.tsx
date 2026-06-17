import { useEffect, useState } from 'react';
import { 
  CalendarClock, Wrench, CheckCircle, Clock, 
  AlertTriangle, Plus, Server
} from 'lucide-react';
import { getMaintenance } from '../api';
import type { ZabbixMaintenanceOut } from '../types';

export function MaintenanceCenter() {
  const [schedules, setSchedules] = useState<ZabbixMaintenanceOut[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchMaintenance();
  }, []);

  const fetchMaintenance = async () => {
    try {
      const data = await getMaintenance();
      setSchedules(data);
    } catch (err) {
      console.error('Failed to fetch maintenance', err);
    } finally {
      setLoading(false);
    }
  };

  const getUrgencyColor = (isOverdue: boolean, daysUntilDue?: number | null) => {
    if (isOverdue) return 'text-rose-400 border-rose-500/30 bg-rose-500/10';
    if (daysUntilDue !== null && daysUntilDue !== undefined && daysUntilDue <= 7) 
      return 'text-amber-400 border-amber-500/30 bg-amber-500/10';
    return 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10';
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <CalendarClock className="w-5 h-5 text-indigo-400" />
            Maintenance Center
          </h1>
          <p className="text-xs text-slate-400 mt-1">Preventive maintenance schedules and tracking</p>
        </div>
        
        <button className="flex items-center gap-2 px-4 py-2 bg-indigo-500 hover:bg-indigo-600 text-white text-sm font-medium rounded-lg transition shrink-0">
          <Plus className="w-4 h-4" />
          Schedule Maintenance
        </button>
      </div>

      {loading ? (
        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-12 flex items-center justify-center text-slate-400">
          <Wrench className="w-6 h-6 animate-pulse mr-2" />
          Loading schedules...
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {schedules.length === 0 ? (
            <div className="col-span-full p-8 text-center bg-slate-900/50 border border-slate-800 rounded-xl">
              <CheckCircle className="w-12 h-12 text-emerald-500/50 mx-auto mb-3" />
              <p className="text-slate-300 font-medium">No Maintenance Scheduled</p>
              <p className="text-xs text-slate-500 mt-1">Add a schedule to track preventive maintenance.</p>
            </div>
          ) : (
            schedules.map(maint => (
              <div key={maint.id} className={`bg-slate-900/50 border rounded-xl overflow-hidden transition-all hover:bg-slate-800/40 ${getUrgencyColor(maint.is_overdue, maint.days_until_due).split(' ')[1]}`}>
                
                <div className="px-5 py-4 border-b border-slate-800/50 flex justify-between items-start">
                  <div className="flex items-start gap-3">
                    <div className={`mt-0.5 w-8 h-8 rounded-lg flex items-center justify-center shrink-0 border ${getUrgencyColor(maint.is_overdue, maint.days_until_due)}`}>
                      <Wrench className="w-4 h-4" />
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-slate-200">{maint.task_type}</h3>
                      <div className="flex items-center gap-1.5 mt-1 text-xs text-slate-400 font-medium">
                        <Server className="w-3.5 h-3.5" />
                        {maint.hostname}
                      </div>
                    </div>
                  </div>
                </div>

                <div className="px-5 py-4 space-y-4">
                  {/* Urgency Alert */}
                  {(maint.is_overdue || (maint.days_until_due !== null && maint.days_until_due !== undefined && maint.days_until_due <= 7)) && (
                    <div className={`flex items-center gap-2 p-2.5 rounded-lg text-xs font-semibold ${getUrgencyColor(maint.is_overdue, maint.days_until_due)}`}>
                      <AlertTriangle className="w-4 h-4 shrink-0" />
                      {maint.is_overdue 
                        ? `OVERDUE BY ${Math.abs(maint.days_until_due || 0)} DAYS` 
                        : `DUE IN ${maint.days_until_due} DAYS`
                      }
                    </div>
                  )}

                  <div className="grid grid-cols-2 gap-4 text-xs">
                    <div>
                      <span className="block text-[10px] uppercase tracking-wider text-slate-500 mb-1 font-semibold">Next Maintenance</span>
                      <div className="flex items-center gap-1.5 text-slate-200 font-medium">
                        <Clock className="w-3.5 h-3.5 text-indigo-400" />
                        {new Date(maint.next_maintenance_date).toLocaleDateString()}
                      </div>
                    </div>
                    <div>
                      <span className="block text-[10px] uppercase tracking-wider text-slate-500 mb-1 font-semibold">Interval</span>
                      <div className="flex items-center gap-1.5 text-slate-300">
                        {maint.interval_days} Days
                      </div>
                    </div>
                  </div>

                  <div className="pt-3 border-t border-slate-800/50 flex items-center justify-between">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider border ${
                      maint.status === 'Completed' ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20' :
                      'text-indigo-400 bg-indigo-500/10 border-indigo-500/20'
                    }`}>
                      {maint.status}
                    </span>
                    <button className="text-[11px] font-medium text-slate-400 hover:text-white transition">
                      Edit details
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
