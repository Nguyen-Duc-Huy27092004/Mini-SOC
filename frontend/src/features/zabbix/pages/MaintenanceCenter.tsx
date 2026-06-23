import { useEffect, useState } from 'react';
import { 
  CalendarClock, Wrench, CheckCircle, Clock, 
  AlertTriangle, Plus, Server
} from 'lucide-react';
import { getMaintenance, createMaintenance } from '../api';
import type { ZabbixMaintenanceOut, ZabbixMaintenanceCreate } from '../types';

export function MaintenanceCenter() {
  const [schedules, setSchedules] = useState<ZabbixMaintenanceOut[]>([]);
  const [loading, setLoading] = useState(true);

  // Modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formData, setFormData] = useState<ZabbixMaintenanceCreate>({
    hostname: '',
    task_type: '',
    next_maintenance_date: new Date().toISOString().split('T')[0],
    interval_days: 30,
    status: 'Scheduled',
    assigned_to: '',
    notes: '',
  });

  const handleOpenModal = () => {
    setFormData({
      hostname: '',
      task_type: '',
      next_maintenance_date: new Date().toISOString().split('T')[0],
      interval_days: 30,
      status: 'Scheduled',
      assigned_to: '',
      notes: '',
    });
    setIsModalOpen(true);
  };

  const handleCloseModal = () => setIsModalOpen(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setIsSubmitting(true);
      await createMaintenance(formData);
      await fetchMaintenance();
      handleCloseModal();
    } catch (error) {
      console.error('Failed to create maintenance:', error);
      alert('Failed to schedule maintenance. Please check the console for details.');
    } finally {
      setIsSubmitting(false);
    }
  };


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
            Trung tâm bảo trì
          </h1>
          <p className="text-xs text-slate-400 mt-1">Lịch trình và theo dõi bảo trì phòng ngừa</p>
        </div>
        
        <button 
          onClick={handleOpenModal}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-500 hover:bg-indigo-600 text-white text-sm font-medium rounded-lg transition shrink-0"
        >
          <Plus className="w-4 h-4" />
          Lên lịch bảo trì
        </button>
      </div>

      {loading ? (
        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-12 flex items-center justify-center text-slate-400">
          <Wrench className="w-6 h-6 animate-pulse mr-2" />
          Đang tải lịch bảo trì...
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {schedules.length === 0 ? (
            <div className="col-span-full p-8 text-center bg-slate-900/50 border border-slate-800 rounded-xl">
              <CheckCircle className="w-12 h-12 text-emerald-500/50 mx-auto mb-3" />
              <p className="text-slate-300 font-medium">Không có lịch bảo trì nào</p>
              <p className="text-xs text-slate-500 mt-1">Thêm lịch bảo trì để theo dõi bảo trì phòng ngừa.</p>
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
                        ? `QUÁ HẠN ${Math.abs(maint.days_until_due || 0)} NGÀY` 
                        : `CÒN ${maint.days_until_due} NGÀY`
                      }
                    </div>
                  )}

                  <div className="grid grid-cols-2 gap-4 text-xs">
                    <div>
                      <span className="block text-[10px] uppercase tracking-wider text-slate-500 mb-1 font-semibold"> Lần bảo trì tiếp theo</span>
                      <div className="flex items-center gap-1.5 text-slate-200 font-medium">
                        <Clock className="w-3.5 h-3.5 text-indigo-400" />
                        {new Date(maint.next_maintenance_date).toLocaleDateString()}
                      </div>
                    </div>
                    <div>
                      <span className="block text-[10px] uppercase tracking-wider text-slate-500 mb-1 font-semibold">Khoảng cách</span>
                      <div className="flex items-center gap-1.5 text-slate-300">
                        {maint.interval_days} Ngày
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
                      Chỉnh sửa chi tiết 
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Schedule Maintenance Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-700 rounded-xl w-full max-w-2xl overflow-hidden shadow-2xl flex flex-col max-h-[90vh]">
            <div className="p-6 border-b border-slate-800 flex justify-between items-center">
              <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
                <CalendarClock className="w-5 h-5 text-indigo-400" />
                Lịch bảo trì 
              </h2>
              <button onClick={handleCloseModal} className="text-slate-400 hover:text-slate-200">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            
            <div className="p-6 overflow-y-auto">
              <form id="add-maintenance-form" onSubmit={handleSubmit} className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-1 md:col-span-2">
                    <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Máy chủ *</label>
                    <input required type="text" value={formData.hostname} onChange={e => setFormData({...formData, hostname: e.target.value})} className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-200 focus:border-indigo-500 focus:outline-none" placeholder="server-01" />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Giao việc *</label>
                    <input required type="text" value={formData.task_type} onChange={e => setFormData({...formData, task_type: e.target.value})} className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-200 focus:border-indigo-500 focus:outline-none" placeholder="OS Patching" />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Giao cho</label>
                    <input type="text" value={formData.assigned_to || ''} onChange={e => setFormData({...formData, assigned_to: e.target.value})} className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-200 focus:border-indigo-500 focus:outline-none" placeholder="john.doe@example.com" />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Lần bảo trì tiếp theo *</label>
                    <input required type="date" value={formData.next_maintenance_date} onChange={e => setFormData({...formData, next_maintenance_date: e.target.value})} className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-200 focus:border-indigo-500 focus:outline-none" />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Khoảng cách bảo trì (Ngày) *</label>
                    <input required type="number" min="1" value={formData.interval_days} onChange={e => setFormData({...formData, interval_days: parseInt(e.target.value) || 30})} className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-200 focus:border-indigo-500 focus:outline-none" />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Trạng thái </label>
                    <select value={formData.status} onChange={e => setFormData({...formData, status: e.target.value})} className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-200 focus:border-indigo-500 focus:outline-none">
                      <option value="Scheduled">Đã lên lịch</option>
                      <option value="In Progress">Đang trong quá trình</option>
                      <option value="Completed">Đã hoàn thành</option>
                      <option value="Cancelled">Đã hủy</option>
                    </select>
                  </div>
                  <div className="space-y-1 md:col-span-2">
                    <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Ghi chú</label>
                    <textarea value={formData.notes || ''} onChange={e => setFormData({...formData, notes: e.target.value})} className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-200 focus:border-indigo-500 focus:outline-none" rows={3} placeholder="Yêu cầu hoặc chi tiết..." />
                  </div>
                </div>
              </form>
            </div>
            
            <div className="p-6 border-t border-slate-800 flex justify-end gap-3 bg-slate-900/50 mt-auto">
              <button 
                type="button"
                onClick={handleCloseModal}
                className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white transition"
              >
                Hủy
              </button>
              <button 
                type="submit"
                form="add-maintenance-form"
                disabled={isSubmitting}
                className="px-4 py-2 bg-indigo-500 hover:bg-indigo-600 text-white text-sm font-medium rounded-lg transition disabled:opacity-50 flex items-center gap-2"
              >
                {isSubmitting ? 'Đang lưu...' : 'Lưu lịch'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
