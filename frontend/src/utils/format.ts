/**
 * Formatting Utilities for SOC Portal
 */

export const formatBytes = (bytes: number, decimals: number = 2): string => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
};

export const formatPercent = (value: number): string => {
  return `${value.toFixed(1)}%`;
};

export const formatDateTime = (isoString: string): string => {
  if (!isoString) return 'Chưa ghi nhận';
  try {
    const d = new Date(isoString);
    // Return format: DD/MM/YYYY HH:MM:SS
    const day = String(d.getDate()).padStart(2, '0');
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const year = d.getFullYear();
    const hours = String(d.getHours()).padStart(2, '0');
    const minutes = String(d.getMinutes()).padStart(2, '0');
    const seconds = String(d.getSeconds()).padStart(2, '0');
    return `${day}/${month}/${year} ${hours}:${minutes}:${seconds}`;
  } catch (e) {
    return isoString;
  }
};

export const getSeverityLabel = (severity: string): string => {
  const labels: Record<string, string> = {
    critical: 'Nguy cấp',
    high: 'Cao',
    medium: 'Trung bình',
    low: 'Thấp'
  };
  return labels[severity.toLowerCase()] || severity;
};

export const getSeverityColor = (severity: string): string => {
  const colors: Record<string, string> = {
    critical: 'text-cyber-critical bg-red-950/40 border-red-900/60',
    high: 'text-cyber-warning bg-amber-950/40 border-amber-900/60',
    medium: 'text-cyber-accent bg-cyan-950/40 border-cyan-900/60',
    low: 'text-cyber-ok bg-emerald-950/40 border-emerald-900/60'
  };
  return colors[severity.toLowerCase()] || 'text-cyber-muted border-cyber-border';
};

export const getSeverityDotColor = (severity: string): string => {
  const colors: Record<string, string> = {
    critical: 'bg-cyber-critical shadow-[0_0_8px_#EF4444]',
    high: 'bg-cyber-warning shadow-[0_0_8px_#F59E0B]',
    medium: 'bg-cyber-accent shadow-[0_0_8px_#06B6D4]',
    low: 'bg-cyber-ok shadow-[0_0_8px_#10B981]'
  };
  return colors[severity.toLowerCase()] || 'bg-cyber-muted';
};
