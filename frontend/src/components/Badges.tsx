import { STAGES } from '../lib/types';

export function StageBadge({ stage }: { stage: string }) {
  const info = STAGES[stage] || { label: stage, color: 'bg-gray-600' };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium text-white ${info.color}`}>
      {info.label}
    </span>
  );
}

export function ResolutionBadge({ resolution }: { resolution: string | null }) {
  if (!resolution) return <span className="text-gray-500 text-sm">--</span>;
  const label = resolution.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  const colorMap: Record<string, string> = {
    issuer_win: 'text-green-400',
    acquirer_win: 'text-red-400',
    split_liability: 'text-yellow-400',
    human_override: 'text-purple-400',
    invalid_dispute: 'text-gray-400',
  };
  return (
    <span className={`text-sm font-medium ${colorMap[resolution] || 'text-gray-300'}`}>
      {label}
    </span>
  );
}

export function ConfidenceMeter({ value }: { value: number | null }) {
  if (value == null) return <span className="text-gray-500 text-sm">--</span>;
  const pct = Math.round(value * 100);
  const color = pct >= 80 ? 'bg-green-500' : pct >= 60 ? 'bg-yellow-500' : 'bg-red-500';
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 bg-gray-700 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-400">{pct}%</span>
    </div>
  );
}
