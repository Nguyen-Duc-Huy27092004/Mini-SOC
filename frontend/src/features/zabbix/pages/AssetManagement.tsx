import { useEffect, useState } from 'react';
import { 
  Server, Activity, Plus, Search, 
  MapPin, ShieldCheck, CalendarClock
} from 'lucide-react';
import { getAssets } from '../api';
import type { ZabbixAssetOut } from '../types';

export function AssetManagement() {
  const [assets, setAssets] = useState<ZabbixAssetOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

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
            Asset Management
          </h1>
          <p className="text-xs text-slate-400 mt-1">Infrastructure inventory and lifecycle tracking</p>
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
          <button className="flex items-center gap-2 px-4 py-2 bg-indigo-500 hover:bg-indigo-600 text-white text-sm font-medium rounded-lg transition">
            <Plus className="w-4 h-4" />
            Add Asset
          </button>
        </div>
      </div>

      <div className="bg-slate-900/50 border border-slate-800 rounded-xl overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center p-12 text-slate-400">
            <Activity className="w-6 h-6 animate-pulse mr-2" />
            Loading asset inventory...
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-900/80 border-b border-slate-800 text-xs uppercase tracking-wider text-slate-500 font-semibold">
                  <th className="px-5 py-4 font-semibold">Hostname / IP</th>
                  <th className="px-5 py-4 font-semibold">Location / Dept</th>
                  <th className="px-5 py-4 font-semibold">Hardware Specs</th>
                  <th className="px-5 py-4 font-semibold">Warranty Expiry</th>
                  <th className="px-5 py-4 font-semibold">Status</th>
                  <th className="px-5 py-4 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50">
                {filteredAssets.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-5 py-8 text-center text-slate-500 text-sm">
                      No assets found matching your criteria.
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
                                ? <span className="text-rose-400">Expired</span> 
                                : 'Active'
                              }
                            </div>
                          </div>
                        ) : (
                          <span className="text-xs text-slate-500 flex items-center gap-1.5">
                            <CalendarClock className="w-3.5 h-3.5" /> No data
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
    </div>
  );
}
