"use client";

import { useCallback, useEffect, useState } from "react";
import JobCard from "@/components/JobCard";
import { api, IngestStats, Job, JobStatus } from "@/lib/api";

const TABS: { label: string; status: JobStatus }[] = [
  { label: "QUEUE", status: "active" },
  { label: "APPLIED", status: "applied" },
  { label: "INTERVIEWING", status: "interviewing" },
  { label: "REJECTED", status: "rejected" },
  { label: "EXPIRED", status: "expired" },
];

function syncSummary(results: IngestStats[]): string {
  const parts = results.map((r) =>
    r.error
      ? `${r.provider}: ERROR`
      : `${r.provider}: +${r.created} new, ${r.filtered} filtered`
  );
  return parts.join(" · ");
}

export default function Home() {
  const [tab, setTab] = useState<JobStatus>("active");
  const [highAlignmentOnly, setHighAlignmentOnly] = useState(false);
  const [threshold, setThreshold] = useState(0.5);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<string | null>(null);

  useEffect(() => {
    api.config().then((c) => setThreshold(c.alignment_threshold)).catch(() => {});
  }, []);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    api
      .jobs(tab, highAlignmentOnly ? threshold : undefined)
      .then(setJobs)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [tab, highAlignmentOnly, threshold]);

  useEffect(load, [load]);

  const sync = async () => {
    setSyncing(true);
    setSyncResult(null);
    try {
      const { results } = await api.runIngest();
      setSyncResult(syncSummary(results));
      load();
    } catch (e) {
      setSyncResult(`SYNC FAILED: ${e}`);
    } finally {
      setSyncing(false);
    }
  };

  return (
    <main className="mx-auto max-w-4xl p-6">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-widest text-cyber-cyan">SYNAPSE</h1>
          <p className="text-xs text-gray-500">TARGET ACQUISITION QUEUE</p>
        </div>
        <div className="flex items-center gap-4">
          <label className="flex cursor-pointer items-center gap-2 text-xs text-gray-400">
            <input
              type="checkbox"
              checked={highAlignmentOnly}
              onChange={(e) => setHighAlignmentOnly(e.target.checked)}
              className="accent-cyan-500"
            />
            ALIGNMENT ≥ {threshold.toFixed(2)}
          </label>
          <button
            onClick={sync}
            disabled={syncing}
            className="border border-cyber-magenta px-4 py-2 text-xs font-bold tracking-wider
                       text-cyber-magenta shadow-glow-magenta transition hover:bg-pink-950
                       disabled:animate-pulse disabled:opacity-60"
          >
            {syncing ? "SYNCING ALL SOURCES…" : "⟳ SYNC SOURCES"}
          </button>
        </div>
      </header>

      {syncResult && (
        <p className="mb-4 border border-gray-700 bg-surface p-2 text-xs text-gray-400">
          {syncResult}
        </p>
      )}

      <nav className="mb-6 flex flex-wrap gap-2">
        {TABS.map((t) => (
          <button
            key={t.status}
            onClick={() => setTab(t.status)}
            className={`border px-3 py-1 text-xs tracking-wider transition ${
              tab === t.status
                ? "border-cyber-cyan text-cyber-cyan shadow-glow-cyan"
                : "border-gray-700 text-gray-500 hover:border-gray-500"
            }`}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {loading && <p className="animate-pulse text-cyber-cyan">SCANNING…</p>}
      {error && (
        <p className="border border-cyber-magenta p-3 text-sm text-cyber-magenta">
          BACKEND OFFLINE: {error}
        </p>
      )}
      {!loading && !error && jobs.length === 0 && (
        <p className="text-gray-500">
          No targets in this queue. Hit ⟳ SYNC SOURCES to pull fresh listings.
        </p>
      )}

      <div className="space-y-3">
        {jobs.map((job) => (
          <JobCard key={job.id} job={job} />
        ))}
      </div>
    </main>
  );
}
