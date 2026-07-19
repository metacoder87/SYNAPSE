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
  first_seen_at: string | null;
  raw_metadata: Record<string, unknown> | null;
}

export interface Dossier {
  dossier_id: string;
  status: "running" | "complete" | "failed";
  content_markdown: string | null;
  error: string | null;
  progress?: string | null;
  citation_coverage?: number | null;
  verified_ratio?: number | null;
  evidence?: { id: string; url: string; title: string }[] | null;
}

export interface StatusEvent {
  id: string;
  event_type: "status" | "note";
  status: JobStatus | null;
  note: string | null;
  created_at: string;
}

export interface Artifact {
  artifact_id: string;
  status: "running" | "complete" | "failed";
  content_markdown: string | null;
  error: string | null;
}

export type ArtifactKind = "tailor" | "interview";

export interface ScoreExplanation {
  alignment_score: number | null;
  top_matches: { phrase: string; similarity: number }[];
}

export const TOKEN_KEY = "synapse.token";

export function authHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem(TOKEN_KEY);
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...authHeaders(), ...init?.headers },
  });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json();
}

/** Download an authenticated export as a file (F9). */
export async function downloadExport(path: string, filename: string): Promise<void> {
  const res = await fetch(`${BASE}${path}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
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
      `/jobs?status=${status}&limit=500${minScore != null ? `&min_score=${minScore}` : ""}`
    ),
  job: (id: string) => request<Job>(`/jobs/${id}`),
  setStatus: (id: string, status: JobStatus) =>
    request(`/jobs/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),
  config: () => request<{ alignment_threshold: number }>(`/config`),
  events: (id: string) => request<StatusEvent[]>(`/jobs/${id}/events`),
  addNote: (id: string, note: string) =>
    request(`/jobs/${id}/notes`, { method: "POST", body: JSON.stringify({ note }) }),
  explain: (id: string) => request<ScoreExplanation>(`/jobs/${id}/explain`),
  settingsFile: (name: string) =>
    request<{ name: string; content: string }>(`/settings/files/${name}`),
  saveSettingsFile: (name: string, content: string) =>
    request<{ name: string; status: string }>(`/settings/files/${name}`, {
      method: "PUT",
      body: JSON.stringify({ content }),
    }),
  artifacts: (id: string) =>
    request<Partial<Record<ArtifactKind, Artifact>>>(`/jobs/${id}/artifacts`),
  startArtifact: (id: string, kind: ArtifactKind) =>
    request<{ artifact_id: string; status: string }>(`/jobs/${id}/artifacts/${kind}`, {
      method: "POST",
    }),
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
