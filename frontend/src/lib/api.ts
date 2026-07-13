/** API client for the SYNAPSE backend (proxied via next.config rewrites). */

const BASE = "/api/backend";

export type JobStatus = "active" | "expired" | "applied" | "interviewing" | "rejected";

export interface Job {
  id: string;
  source_provider: string;
  title: string;
  company: string;
  department: string | null;
  location_string: string | null;
  is_remote: boolean;
  job_url: string;
  apply_url: string | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_interval: string | null;
  security_clearance: string | null;
  alignment_score: number | null;
  description_markdown: string;
  posted_at: string | null;
  closing_date: string | null;
  system_status: JobStatus;
}

export interface Dossier {
  dossier_id: string;
  status: "running" | "complete" | "failed";
  content_markdown: string | null;
  error: string | null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json();
}

export interface IngestStats {
  provider: string;
  fetched: number;
  parsed: number;
  parse_failed: number;
  filtered: number;
  created: number;
  refreshed: number;
  persist_failed: number;
  error: string | null;
}

export const api = {
  runIngest: () =>
    request<{ results: IngestStats[] }>(`/ingest/run`, { method: "POST" }),
  jobs: (status: JobStatus = "active", minScore?: number) =>
    request<Job[]>(
      `/jobs?status=${status}${minScore != null ? `&min_score=${minScore}` : ""}`
    ),
  job: (id: string) => request<Job>(`/jobs/${id}`),
  setStatus: (id: string, status: JobStatus) =>
    request(`/jobs/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),
  config: () => request<{ alignment_threshold: number }>(`/config`),
  startDeepDive: (id: string) =>
    request<{ dossier_id: string; status: string }>(`/jobs/${id}/deep-dive`, {
      method: "POST",
    }),
  dossier: (id: string) => request<Dossier>(`/jobs/${id}/dossier`),
};

export function formatSalary(job: Job): string | null {
  if (!job.salary_min && !job.salary_max) return null;
  const fmt = (n: number) => `$${Math.round(n / 1000)}k`;
  const range = [job.salary_min, job.salary_max]
    .filter((n): n is number => n != null)
    .map(fmt)
    .join("–");
  return job.salary_interval === "PA" || job.salary_interval === "year"
    ? `${range}/yr`
    : range;
}
