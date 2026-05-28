import { useEffect, useState } from 'react';
import api from '../shared/api/client';

export function GenericDataPage({ title, endpoint }: { title: string; endpoint: string }) {
  const [data, setData] = useState<unknown>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get(endpoint).then((r) => setData(r.data)).catch((e) => setError(e.message));
  }, [endpoint]);

  return (
    <div>
      <h2 className="text-lg font-bold mb-4">{title}</h2>
      {error && <p className="text-cyber-critical">{error}</p>}
      {!data && !error && <p className="text-cyber-muted">Đang tải...</p>}
      {data !== null && data !== undefined && (
        <pre className="p-4 rounded-lg bg-slate-950 border border-cyber-border text-xs overflow-auto max-h-[70vh]">
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  );
}
