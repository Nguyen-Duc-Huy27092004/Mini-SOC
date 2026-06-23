import { useEffect, useState } from 'react';
import { 
  Server, Activity, Plus, Search, 
  MapPin, ShieldCheck, CalendarClock
} from 'lucide-react';
import { getAssets, createAsset } from '../api';
import type { ZabbixAssetOut, ZabbixAssetCreate } from '../types';

export function AssetManagement() {
  const [assets, setAssets] = useState<ZabbixAssetOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  
  // Modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formData, setFormData] = useState<ZabbixAssetCreate>({
    hostname: '',
    ip_address: '',
    location: '',
    department: '',
    vendor: '',
    model: '',
    serial_number: '',
    lifecycle_status: 'Active',
    notes: '',
  });

  const handleOpenModal = () => {
    setFormData({
      hostname: '',
      ip_address: '',
      location: '',
      department: '',
      vendor: '',
      model: '',
      serial_number: '',
      lifecycle_status: 'Active',
      notes: '',
    });
    setIsModalOpen(true);
  };

  const handleCloseModal = () => setIsModalOpen(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setIsSubmitting(true);
      await createAsset(formData);
      await fetchAssets();
      handleCloseModal();
    } catch (error) {
      console.error('Failed to create asset:', error);
      alert('Failed to create asset. Please check the console for details.');
    } finally {
      setIsSubmitting(false);
    }
  };


  useEffect(() => {
    fetchAssets();
  }, []);

  const fetchAssets = async () => {
    try {
      const data = await getAssets();
      setAssets(data);
    } catch (err) {
      console.error('Failed to fetch assets', err);
    } finally {
      setLoading(false);
    }
  };

  const getStatusStyle = (status: string) => {
    switch (status.toLowerCase()) {
      case 'active': return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20';
      case 'maintenance': return 'text-amber-400 bg-amber-500/10 border-amber-500/20';
      case 'end of life': return 'text-rose-400 bg-rose-500/10 border-rose-500/20';
      default: return 'text-slate-400 bg-slate-500/10 border-slate-500/20';
    }
  };

  const filteredAssets = assets.filter(a => 
    a.hostname.toLowerCase().includes(search.toLowerCase()) ||
    (a.ip_address && a.ip_address.includes(search)) ||
    (a.department && a.department.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <Server className="w-5 h-5 text-indigo-400" />
            Quản lý tài sản CNTT
          </h1>
          <p className="text-xs text-slate-400 mt-1">Quản lý thông tin tài sản CNTT</p>
        </div>
        
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input 
              type="text"
              placeholder="Search assets..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="pl-9 pr-4 py-2 bg-slate-900 border border-slate-800 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-indigo-500 w-64 transition"
            />
          </div>
          <button 
            onClick={handleOpenModal}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-500 hover:bg-indigo-600 text-white text-sm font-medium rounded-lg transition"
          >
            <Plus className="w-4 h-4" />
            Thêm tài sản
          </button>
        </div>
      </div>

      <div className="bg-slate-900/50 border border-slate-800 rounded-xl overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center p-12 text-slate-400">
            <Activity className="w-6 h-6 animate-pulse mr-2" />
            Đang tải danh sách tài sản...
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-900/80 border-b border-slate-800 text-xs uppercase tracking-wider text-slate-500 font-semibold">
                  <th className="px-5 py-4 font-semibold">Tên tài sản / IP</th>
                  <th className="px-5 py-4 font-semibold">Vị trí / Bộ phận</th>
                  <th className="px-5 py-4 font-semibold">Thông tin phần cứng</th>
                  <th className="px-5 py-4 font-semibold">Ngày hết hạn bảo hành</th>
                  <th className="px-5 py-4 font-semibold">Trạng thái</th>
                  <th className="px-5 py-4 font-semibold text-right">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50">
                {filteredAssets.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-5 py-8 text-center text-slate-500 text-sm">
                      Không tìm thấy tài sản nào phù hợp với yêu cầu tìm kiếm.
                    </td>
                  </tr>
                ) : (
                  filteredAssets.map(asset => (
                    <tr key={asset.id} className="hover:bg-slate-800/20 transition">
                      <td className="px-5 py-4">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-lg bg-slate-950 border border-slate-800 flex items-center justify-center shrink-0">
                            <Server className="w-4 h-4 text-indigo-400" />
                          </div>
                          <div>
                            <div className="font-semibold text-sm text-slate-200">{asset.hostname}</div>
                            <div className="text-[10px] font-mono text-slate-500 mt-0.5">{asset.ip_address || 'No IP specified'}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-4">
                        <div className="flex items-center gap-1.5 text-xs text-slate-300">
                          <MapPin className="w-3.5 h-3.5 text-slate-500" />
                          {asset.location || 'Unknown'}
                        </div>
                        <div className="text-[10px] text-slate-500 mt-1 uppercase tracking-wider">
                          {asset.department || 'Unassigned'}
                        </div>
                      </td>
                      <td className="px-5 py-4">
                        <div className="text-xs text-slate-300">
                          {asset.vendor || 'Unknown Vendor'} <span className="text-slate-500">—</span> {asset.model || 'Unknown Model'}
                        </div>
                        <div className="text-[10px] text-slate-500 mt-1 font-mono uppercase">
                          SN: {asset.serial_number || 'N/A'}
                        </div>
                      </td>
                      <td className="px-5 py-4">
                        {asset.warranty_expiration ? (
                          <div>
                            <div className="flex items-center gap-1.5 text-xs text-slate-300">
                              <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
                              {new Date(asset.warranty_expiration).toLocaleDateString()}
                            </div>
                            <div className="text-[10px] text-slate-500 mt-1">
                              {new Date() > new Date(asset.warranty_expiration) 
                                ? <span className="text-rose-400">Hết hạn</span> 
                                : 'Active'
                              }
                            </div>
                          </div>
                        ) : (
                          <span className="text-xs text-slate-500 flex items-center gap-1.5">
                            <CalendarClock className="w-3.5 h-3.5" /> Không có dữ liệu
                          </span>
                        )}
                      </td>
                      <td className="px-5 py-4">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold tracking-wider uppercase border ${getStatusStyle(asset.lifecycle_status)}`}>
                          {asset.lifecycle_status}
                        </span>
                      </td>
                      <td className="px-5 py-4 text-right">
                        <button className="text-[11px] font-medium text-indigo-400 hover:text-indigo-300 transition">Edit</button>
                        <span className="text-slate-700 mx-2">|</span>
                        <button className="text-[11px] font-medium text-rose-400 hover:text-rose-300 transition">Delete</button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Add Asset Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-700 rounded-xl w-full max-w-2xl overflow-hidden shadow-2xl flex flex-col max-h-[90vh]">
            <div className="p-6 border-b border-slate-800 flex justify-between items-center">
              <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
                <Server className="w-5 h-5 text-indigo-400" />
                Add New Asset
              </h2>
              <button onClick={handleCloseModal} className="text-slate-400 hover:text-slate-200">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            
            <div className="p-6 overflow-y-auto">
              <form id="add-asset-form" onSubmit={handleSubmit} className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Hostname *</label>
                    <input required type="text" value={formData.hostname} onChange={e => setFormData({...formData, hostname: e.target.value})} className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-200 focus:border-indigo-500 focus:outline-none" placeholder="server-01" />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">IP Address</label>
                    <input type="text" value={formData.ip_address || ''} onChange={e => setFormData({...formData, ip_address: e.target.value})} className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-200 focus:border-indigo-500 focus:outline-none" placeholder="192.168.1.100" />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Location</label>
                    <input type="text" value={formData.location || ''} onChange={e => setFormData({...formData, location: e.target.value})} className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-200 focus:border-indigo-500 focus:outline-none" placeholder="Data Center A" />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Department</label>
                    <input type="text" value={formData.department || ''} onChange={e => setFormData({...formData, department: e.target.value})} className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-200 focus:border-indigo-500 focus:outline-none" placeholder="Engineering" />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Vendor</label>
                    <input type="text" value={formData.vendor || ''} onChange={e => setFormData({...formData, vendor: e.target.value})} className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-200 focus:border-indigo-500 focus:outline-none" placeholder="Dell" />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Model</label>
                    <input type="text" value={formData.model || ''} onChange={e => setFormData({...formData, model: e.target.value})} className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-200 focus:border-indigo-500 focus:outline-none" placeholder="PowerEdge R740" />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Serial Number</label>
                    <input type="text" value={formData.serial_number || ''} onChange={e => setFormData({...formData, serial_number: e.target.value})} className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-200 focus:border-indigo-500 focus:outline-none" placeholder="SN123456" />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Lifecycle Status</label>
                    <select value={formData.lifecycle_status} onChange={e => setFormData({...formData, lifecycle_status: e.target.value})} className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-200 focus:border-indigo-500 focus:outline-none">
                      <option value="Active">Active</option>
                      <option value="Maintenance">Maintenance</option>
                      <option value="End of Life">End of Life</option>
                      <option value="Decommissioned">Decommissioned</option>
                    </select>
                  </div>
                  <div className="space-y-1 md:col-span-2">
                    <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Notes</label>
                    <textarea value={formData.notes || ''} onChange={e => setFormData({...formData, notes: e.target.value})} className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-200 focus:border-indigo-500 focus:outline-none" rows={3} placeholder="Additional details..." />
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
                Cancel
              </button>
              <button 
                type="submit"
                form="add-asset-form"
                disabled={isSubmitting}
                className="px-4 py-2 bg-indigo-500 hover:bg-indigo-600 text-white text-sm font-medium rounded-lg transition disabled:opacity-50 flex items-center gap-2"
              >
                {isSubmitting ? 'Saving...' : 'Save Asset'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
