"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import JobCard from "@/components/JobCard";
import { api, IngestStats, Job, JobStatus } from "@/lib/api";

const TABS: { label: string; status: JobStatus }[] = [
  { label: "QUEUE", status: "active" },
  { label: "APPLIED", status: "applied" },
  { label: "INTERVIEWING", status: "interviewing" },
  { label: "REJECTED", status: "rejected" },
  { label: "EXPIRED", status: "expired" },
];

type SortKey = "score" | "posted" | "closing" | "pay";
const SORTS: { key: SortKey; label: string }[] = [
  { key: "score", label: "SCORE" },
  { key: "posted", label: "POSTED" },
  { key: "closing", label: "CLOSING" },
  { key: "pay", label: "PAY" },
];

const PREFS_KEY = "synapse.prefs.v1";
const LAST_VISIT_KEY = "synapse.lastVisit";

interface Prefs {
  tab: JobStatus;
  sortKey: SortKey;
  sortAsc: boolean;
  remoteOnly: boolean;
  cityFilter: string | null;
  highAlignmentOnly: boolean;
}

const DEFAULT_PREFS: Prefs = {
  tab: "active",
  sortKey: "score",
  sortAsc: false,
  remoteOnly: false,
  cityFilter: null,
  highAlignmentOnly: false,
};

function syncSummary(results: IngestStats[]): string {
  return results
    .map((r) =>
      r.error
        ? `${r.provider}: ERROR`
        : `${r.provider}: +${r.created} new, ${r.filtered} filtered`
    )
    .join(" · ");
}

function cityOf(job: Job): string | null {
  const loc = job.location_string?.trim();
  if (!loc) return null;
  return loc.split(",")[0].replace(/\(.*\)/, "").trim() || null;
}

function sortValue(job: Job, key: SortKey): number | null {
  switch (key) {
    case "score":
      return job.alignment_score;
    case "posted":
      return job.posted_at ? Date.parse(job.posted_at) : null;
    case "closing":
      return job.closing_date ? Date.parse(job.closing_date) : null;
    case "pay":
      return job.salary_max ?? job.salary_min;
  }
}

export default function Home() {
  const [prefs, setPrefs] = useState<Prefs>(DEFAULT_PREFS);
  const [hydrated, setHydrated] = useState(false);
  const [newCutoff, setNewCutoff] = useState<number | null>(null);

  const [threshold, setThreshold] = useState(0.5);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<string | null>(null);

  // U5: restore preferences · U3: NEW-since-last-visit cutoff
  useEffect(() => {
    try {
      const saved = localStorage.getItem(PREFS_KEY);
      if (saved) setPrefs({ ...DEFAULT_PREFS, ...JSON.parse(saved) });
      const lastVisit = localStorage.getItem(LAST_VISIT_KEY);
      setNewCutoff(lastVisit ? Number(lastVisit) : null);
      localStorage.setItem(LAST_VISIT_KEY, String(Date.now()));
    } catch {}
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (hydrated) {
      try {
        localStorage.setItem(PREFS_KEY, JSON.stringify(prefs));
      } catch {}
    }
  }, [prefs, hydrated]);

  const set = <K extends keyof Prefs>(key: K, value: Prefs[K]) =>
    setPrefs((p) => ({ ...p, [key]: value }));

  useEffect(() => {
    api.config().then((c) => setThreshold(c.alignment_threshold)).catch(() => {});
  }, []);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    api
      .jobs(prefs.tab, prefs.highAlignmentOnly ? threshold : undefined)
      .then(setJobs)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [prefs.tab, prefs.highAlignmentOnly, threshold]);

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

  const isNew = (job: Job): boolean =>
    newCutoff != null &&
    job.first_seen_at != null &&
    Date.parse(job.first_seen_at) > newCutoff;

  const cities = useMemo(() => {
    const counts = new Map<string, number>();
    for (const j of jobs) {
      const c = cityOf(j);
      if (c) counts.set(c, (counts.get(c) ?? 0) + 1);
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 14);
  }, [jobs]);

  const visibleJobs = useMemo(() => {
    let list = jobs;
    if (prefs.remoteOnly) list = list.filter((j) => j.is_remote);
    if (prefs.cityFilter) list = list.filter((j) => cityOf(j) === prefs.cityFilter);
    return [...list].sort((a, b) => {
      const va = sortValue(a, prefs.sortKey);
      const vb = sortValue(b, prefs.sortKey);
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      return prefs.sortAsc ? va - vb : vb - va;
    });
  }, [jobs, prefs.remoteOnly, prefs.cityFilter, prefs.sortKey, prefs.sortAsc]);

  const newCount = useMemo(() => jobs.filter(isNew).length, [jobs, newCutoff]);

  return (
    <main className="mx-auto max-w-4xl p-6">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-widest text-cyber-cyan">SYNAPSE</h1>
          <p className="text-xs text-gray-500">
            TARGET ACQUISITION QUEUE
            {newCount > 0 && (
              <span className="ml-2 text-cyber-magenta">▲ {newCount} NEW SINCE LAST VISIT</span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-4">
          <a href="/settings" className="text-xs text-gray-500 transition hover:text-cyber-cyan">
            ⚙ SETTINGS
          </a>
          <label className="flex cursor-pointer items-center gap-2 text-xs text-gray-400">
            <input
              type="checkbox"
              checked={prefs.highAlignmentOnly}
              onChange={(e) => set("highAlignmentOnly", e.target.checked)}
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

      <nav className="mb-4 flex flex-wrap gap-2">
        {TABS.map((t) => (
          <button
            key={t.status}
            onClick={() => set("tab", t.status)}
            className={`border px-3 py-1 text-xs tracking-wider transition ${
              prefs.tab === t.status
                ? "border-cyber-cyan text-cyber-cyan shadow-glow-cyan"
                : "border-gray-700 text-gray-500 hover:border-gray-500"
            }`}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <div className="mb-3 flex flex-wrap items-center gap-2 text-xs">
        <span className="text-gray-600">SORT:</span>
        {SORTS.map((s) => (
          <button
            key={s.key}
            onClick={() => {
              if (prefs.sortKey === s.key) set("sortAsc", !prefs.sortAsc);
              else {
                setPrefs((p) => ({ ...p, sortKey: s.key, sortAsc: s.key === "closing" }));
              }
            }}
            className={`border px-2 py-1 tracking-wider transition ${
              prefs.sortKey === s.key
                ? "border-cyber-magenta text-cyber-magenta"
                : "border-gray-700 text-gray-500 hover:border-gray-500"
            }`}
          >
            {s.label} {prefs.sortKey === s.key ? (prefs.sortAsc ? "↑" : "↓") : ""}
          </button>
        ))}
      </div>

      <div className="mb-6 flex flex-wrap items-center gap-2 text-xs">
        <span className="text-gray-600">WHERE:</span>
        <button
          onClick={() => setPrefs((p) => ({ ...p, cityFilter: null, remoteOnly: false }))}
          className={`border px-2 py-1 transition ${
            !prefs.cityFilter && !prefs.remoteOnly
              ? "border-cyber-cyan text-cyber-cyan"
              : "border-gray-700 text-gray-500 hover:border-gray-500"
          }`}
        >
          ALL
        </button>
        <button
          onClick={() =>
            setPrefs((p) => ({ ...p, remoteOnly: !p.remoteOnly, cityFilter: null }))
          }
          className={`border px-2 py-1 transition ${
            prefs.remoteOnly
              ? "border-cyber-cyan text-cyber-cyan shadow-glow-cyan"
              : "border-gray-700 text-gray-500 hover:border-gray-500"
          }`}
        >
          ⌂ REMOTE
        </button>
        {cities.map(([city, n]) => (
          <button
            key={city}
            onClick={() =>
              setPrefs((p) => ({
                ...p,
                cityFilter: p.cityFilter === city ? null : city,
                remoteOnly: false,
              }))
            }
            className={`border px-2 py-1 transition ${
              prefs.cityFilter === city
                ? "border-cyber-cyan text-cyber-cyan"
                : "border-gray-700 text-gray-500 hover:border-gray-500"
            }`}
          >
            {city} ({n})
          </button>
        ))}
      </div>

      {loading && <p className="animate-pulse text-cyber-cyan">SCANNING…</p>}
      {error && (
        <p className="border border-cyber-magenta p-3 text-sm text-cyber-magenta">
          BACKEND OFFLINE: {error}
        </p>
      )}
      {!loading && !error && visibleJobs.length === 0 && (
        <p className="text-gray-500">
          {jobs.length === 0
            ? "No targets in this queue. Hit ⟳ SYNC SOURCES to pull fresh listings."
            : "No targets match the current filters."}
        </p>
      )}

      <div className="space-y-3">
        {visibleJobs.map((job) => (
          <JobCard key={job.id} job={job} isNew={isNew(job)} />
        ))}
      </div>
    </main>
  );
}
