import { LucideIcon } from 'lucide-react';

interface Props {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  accent?: string;
}

export function KpiCard({ title, value, subtitle, icon: Icon, accent = 'text-cyan-400' }: Props) {
  return (
    <div className="p-5 rounded-xl border border-slate-700/80 bg-slate-900/60 backdrop-blur transition hover:border-cyan-500/30">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs text-slate-400 uppercase tracking-wide">{title}</p>
          <p className="text-3xl font-bold mt-2 text-white tabular-nums">{value}</p>
          {subtitle && <p className="text-xs text-slate-500 mt-1">{subtitle}</p>}
        </div>
        <div className={`p-2.5 rounded-lg bg-slate-800/80 shrink-0 ${accent}`}>
          <Icon className="w-5 h-5" />
        </div>
      </div>
    </div>
  );
}
