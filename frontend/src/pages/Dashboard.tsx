import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Activity, Server, Users, Layers } from 'lucide-react';
import { api } from '../lib/api';
import type { HealthResponse, DisputeSummary } from '../lib/types';
import { CATEGORIES } from '../lib/types';
import { StageBadge, ResolutionBadge, ConfidenceMeter } from '../components/Badges';

function timeAgo(iso: string): string {
  const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

export default function Dashboard() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [disputes, setDisputes] = useState<DisputeSummary[]>([]);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [disputesError, setDisputesError] = useState<string | null>(null);
  const [loadingHealth, setLoadingHealth] = useState(true);
  const [loadingDisputes, setLoadingDisputes] = useState(true);

  useEffect(() => {
    api
      .health()
      .then((data) => {
        setHealth(data);
        setHealthError(null);
      })
      .catch((err) => setHealthError(err.message))
      .finally(() => setLoadingHealth(false));
  }, []);

  useEffect(() => {
    let active = true;

    const fetchDisputes = () => {
      api
        .listDisputes()
        .then((data) => {
          if (active) {
            setDisputes(data);
            setDisputesError(null);
          }
        })
        .catch((err) => {
          if (active) setDisputesError(err.message);
        })
        .finally(() => {
          if (active) setLoadingDisputes(false);
        });
    };

    fetchDisputes();
    const interval = setInterval(fetchDisputes, 5000);

    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <div className="space-y-6">
      {/* Health Banner */}
      <div>
        {loadingHealth && (
          <p className="text-gray-400 text-sm">Loading...</p>
        )}
        {healthError && (
          <p className="text-red-400 text-sm">
            Failed to load health status: {healthError}
          </p>
        )}
        {health && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
              <div className="flex items-center gap-3">
                <Activity className="h-5 w-5 text-gray-400" />
                <div>
                  <p className="text-xs text-gray-500 uppercase tracking-wide">
                    Status
                  </p>
                  <div className="flex items-center gap-2 mt-1">
                    <span
                      className={`h-2 w-2 rounded-full ${
                        health.status === 'healthy'
                          ? 'bg-green-500'
                          : 'bg-red-500'
                      }`}
                    />
                    <span className="text-sm font-medium text-gray-100">
                      {health.status}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
              <div className="flex items-center gap-3">
                <Server className="h-5 w-5 text-gray-400" />
                <div>
                  <p className="text-xs text-gray-500 uppercase tracking-wide">
                    Version
                  </p>
                  <p className="text-sm font-medium text-gray-100 mt-1">
                    {health.version}
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
              <div className="flex items-center gap-3">
                <Users className="h-5 w-5 text-gray-400" />
                <div>
                  <p className="text-xs text-gray-500 uppercase tracking-wide">
                    Agents Loaded
                  </p>
                  <p className="text-sm font-medium text-gray-100 mt-1">
                    {health.agents_loaded}
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
              <div className="flex items-center gap-3">
                <Layers className="h-5 w-5 text-gray-400" />
                <div>
                  <p className="text-xs text-gray-500 uppercase tracking-wide">
                    Queue Depth
                  </p>
                  <p className="text-sm font-medium text-gray-100 mt-1">
                    {health.queue_depth}
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Disputes Table */}
      <div>
        <h2 className="text-lg font-semibold text-gray-100 mb-4">Disputes</h2>

        {loadingDisputes && (
          <p className="text-gray-400 text-sm">Loading...</p>
        )}
        {disputesError && (
          <p className="text-red-400 text-sm">
            Failed to load disputes: {disputesError}
          </p>
        )}

        {!loadingDisputes && !disputesError && disputes.length === 0 && (
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-8 text-center">
            <p className="text-gray-400">
              No disputes yet. Submit one to get started.
            </p>
          </div>
        )}

        {disputes.length > 0 && (
          <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead>
                <tr className="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
                  <th className="px-4 py-3 font-medium">Case ID</th>
                  <th className="px-4 py-3 font-medium">Stage</th>
                  <th className="px-4 py-3 font-medium">Category</th>
                  <th className="px-4 py-3 font-medium">Condition</th>
                  <th className="px-4 py-3 font-medium">Resolution</th>
                  <th className="px-4 py-3 font-medium">Confidence</th>
                  <th className="px-4 py-3 font-medium">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {disputes.map((d) => (
                  <tr
                    key={d.case_id}
                    className="hover:bg-gray-800/50 transition-colors cursor-pointer"
                  >
                    <td className="px-4 py-3">
                      <Link
                        to={`/disputes/${d.case_id}`}
                        className="text-blue-400 hover:text-blue-300 font-mono text-xs"
                      >
                        {d.case_id.slice(0, 8)}...
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <StageBadge stage={d.stage} />
                    </td>
                    <td className="px-4 py-3 text-gray-300">
                      {d.category ? CATEGORIES[d.category] || d.category : '--'}
                    </td>
                    <td className="px-4 py-3 text-gray-300">
                      {d.condition || '--'}
                    </td>
                    <td className="px-4 py-3">
                      <ResolutionBadge resolution={d.resolution} />
                    </td>
                    <td className="px-4 py-3">
                      <ConfidenceMeter value={d.confidence} />
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-xs whitespace-nowrap">
                      {timeAgo(d.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
