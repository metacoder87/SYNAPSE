"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, Artifact, ArtifactKind, Dossier, Job, JobStatus, ScoreExplanation, StatusEvent, formatSalary } from "@/lib/api";
import { markdownComponents } from "@/lib/markdown";

const ACTIONS: { label: string; status: JobStatus; accent: string }[] = [
  { label: "MARK APPLIED", status: "applied", accent: "border-cyber-cyan text-cyber-cyan" },
  { label: "INTERVIEWING", status: "interviewing", accent: "border-cyber-magenta text-cyber-magenta" },
  { label: "REJECT", status: "rejected", accent: "border-gray-600 text-gray-400" },
];

export default function JobDetail() {
  const { id } = useParams<{ id: string }>();
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dossier, setDossier] = useState<Dossier | null>(null);
  const [diving, setDiving] = useState(false);
  const [explanation, setExplanation] = useState<ScoreExplanation | null>(null);
  const [events, setEvents] = useState<StatusEvent[]>([]);
  const [noteDraft, setNoteDraft] = useState("");
  const [artifacts, setArtifacts] = useState<Partial<Record<ArtifactKind, Artifact>>>({});
  const artifactPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    api.job(id).then(setJob).catch((e) => setError(String(e)));
    api.dossier(id).then(setDossier).catch(() => {});
    api.events(id).then(setEvents).catch(() => {});
    api.explain(id).then(setExplanation).catch(() => {});
    api.artifacts(id).then(setArtifacts).catch(() => {});
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      if (artifactPollRef.current) clearInterval(artifactPollRef.current);
    };
  }, [id]);

  const startArtifact = async (kind: ArtifactKind) => {
    try {
      await api.startArtifact(id, kind);
      setArtifacts((a) => ({
        ...a,
        [kind]: { artifact_id: "", status: "running", content_markdown: null, error: null },
      }));
      if (!artifactPollRef.current) {
        artifactPollRef.current = setInterval(async () => {
          try {
            const latest = await api.artifacts(id);
            setArtifacts(latest);
            const anyRunning = Object.values(latest).some((x) => x?.status === "running");
            if (!anyRunning && artifactPollRef.current) {
              clearInterval(artifactPollRef.current);
              artifactPollRef.current = null;
            }
          } catch {}
        }, 4000);
      }
    } catch (e) {
      setError(String(e));
    }
  };

  const poll = useCallback(() => {
    pollRef.current = setInterval(async () => {
      try {
        const d = await api.dossier(id);
        setDossier(d);
        if (d.status !== "running" && pollRef.current) {
          clearInterval(pollRef.current);
          setDiving(false);
        }
      } catch {}
    }, 4000);
  }, [id]);

  const startDive = async () => {
    setDiving(true);
    try {
      await api.startDeepDive(id);
      setDossier({ dossier_id: "", status: "running", content_markdown: null, error: null });
      poll();
    } catch (e) {
      setError(String(e));
      setDiving(false);
    }
  };

  const setStatus = async (status: JobStatus) => {
    await api.setStatus(id, status);
    setJob((j) => (j ? { ...j, system_status: status } : j));
    api.events(id).then(setEvents).catch(() => {});
  };

  const submitNote = async () => {
    const note = noteDraft.trim();
    if (!note) return;
    await api.addNote(id, note);
    setNoteDraft("");
    api.events(id).then(setEvents).catch(() => {});
  };

  if (error) return <main className="p-6 text-cyber-magenta">ERROR: {error}</main>;
  if (!job) return <main className="animate-pulse p-6 text-cyber-cyan">LOADING…</main>;

  const salary = formatSalary(job);

  return (
    <main className="mx-auto max-w-4xl p-6">
      <Link href="/" className="text-xs text-gray-500 hover:text-cyber-cyan">
        ← BACK TO QUEUE
      </Link>

      <header className="mt-4 border border-gray-800 bg-surface p-5 shadow-glow-cyan">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-100">{job.title}</h1>
            <p className="text-cyber-magenta">{job.company}</p>
            <p className="mt-1 text-xs text-gray-500">
              {job.location_string ?? "—"} · {job.source_provider} · status:{" "}
              <span className="text-gray-300">{job.system_status}</span>
            </p>
          </div>
          {job.alignment_score != null && (
            <div className="border border-cyber-cyan px-3 py-2 text-xl font-bold text-cyber-cyan">
              {job.alignment_score.toFixed(3)}
            </div>
          )}
        </div>

        <div className="mt-3 flex flex-wrap gap-2 text-xs">
          {job.is_remote && (
            <span className="border border-cyber-cyan px-2 py-0.5 text-cyber-cyan">REMOTE</span>
          )}
          {salary && <span className="border border-gray-600 px-2 py-0.5">{salary}</span>}
          {job.security_clearance && (
            <span className="border border-cyber-magenta px-2 py-0.5 text-cyber-magenta">
              🔒 {job.security_clearance}
            </span>
          )}
          {job.closing_date && (
            <span className="border border-gray-600 px-2 py-0.5 text-gray-400">
              CLOSES {new Date(job.closing_date).toLocaleDateString()}
            </span>
          )}
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <a
            href={job.apply_url ?? job.job_url}
            target="_blank"
            rel="noopener noreferrer"
            className="border border-cyber-cyan px-4 py-2 text-sm font-bold text-cyber-cyan
                       shadow-glow-cyan transition hover:bg-cyan-950"
          >
            APPLY ↗
          </a>
          <button
            onClick={startDive}
            disabled={diving || dossier?.status === "running"}
            className="border border-cyber-magenta px-4 py-2 text-sm font-bold text-cyber-magenta
                       shadow-glow-magenta transition hover:bg-pink-950 disabled:opacity-40"
          >
            {dossier?.status === "running" ? "AGENTS WORKING…" : "DEEP DIVE"}
          </button>
          <button
            onClick={() => startArtifact("tailor")}
            disabled={artifacts.tailor?.status === "running"}
            className="border border-cyber-cyan px-4 py-2 text-sm font-bold text-cyber-cyan
                       transition hover:bg-cyan-950 disabled:opacity-40"
          >
            {artifacts.tailor?.status === "running" ? "TAILORING…" : "✎ TAILOR RESUME"}
          </button>
          <button
            onClick={() => startArtifact("interview")}
            disabled={artifacts.interview?.status === "running"}
            className="border border-cyber-cyan px-4 py-2 text-sm font-bold text-cyber-cyan
                       transition hover:bg-cyan-950 disabled:opacity-40"
          >
            {artifacts.interview?.status === "running" ? "PREPPING…" : "◉ INTERVIEW PREP"}
          </button>
          {ACTIONS.map((a) => (
            <button
              key={a.status}
              onClick={() => setStatus(a.status)}
              className={`border px-3 py-2 text-xs transition hover:opacity-80 ${a.accent}`}
            >
              {a.label}
            </button>
          ))}
        </div>
      </header>

      {dossier && (
        <section className="mt-6 border border-cyber-magenta bg-surface p-5">
          <h2 className="mb-2 text-sm font-bold tracking-widest text-cyber-magenta">
            ▓ AI DOSSIER {dossier.status === "running" && "— GENERATING (local LLM, be patient)"}
            {dossier.status === "failed" && "— FAILED"}
          </h2>
          {dossier.status === "running" && (
            <p className="animate-pulse text-xs text-gray-500">
              ▸ {dossier.progress ?? "starting research pipeline…"}
            </p>
          )}
          {dossier.status === "complete" &&
            dossier.citation_coverage != null &&
            dossier.verified_ratio != null && (
              <p className="mb-3 text-xs text-gray-500">
                {dossier.evidence?.length ?? 0} sources ·{" "}
                {Math.round(dossier.citation_coverage * 100)}% cited ·{" "}
                {Math.round(dossier.verified_ratio * 100)}% verified
              </p>
            )}
          {dossier.status === "failed" && (
            <p className="text-xs text-cyber-magenta">{dossier.error}</p>
          )}
          {dossier.content_markdown && (
            <article className="text-sm text-gray-300">
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                {dossier.content_markdown}
              </ReactMarkdown>
            </article>
          )}
        </section>
      )}

      {(["tailor", "interview"] as ArtifactKind[]).map((kind) => {
        const art = artifacts[kind];
        if (!art) return null;
        const label = kind === "tailor" ? "TAILOR PACK" : "INTERVIEW PREP";
        return (
          <section key={kind} className="mt-6 border border-cyber-cyan bg-surface p-5">
            <h2 className="mb-2 text-sm font-bold tracking-widest text-cyber-cyan">
              ▓ {label}
              {art.status === "running" && " — GENERATING (local LLM)"}
              {art.status === "failed" && " — FAILED"}
            </h2>
            {art.status === "running" && (
              <p className="animate-pulse text-xs text-gray-500">
                Working from your master resume and profile…
              </p>
            )}
            {art.status === "failed" && (
              <p className="text-xs text-cyber-magenta">{art.error}</p>
            )}
            {art.content_markdown && (
              <article className="text-sm text-gray-300">
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                  {art.content_markdown}
                </ReactMarkdown>
              </article>
            )}
          </section>
        );
      })}

      <section className="mt-6 border border-gray-800 bg-surface p-5">
        <h2 className="mb-2 text-sm font-bold tracking-widest text-gray-400">▓ JOB DESCRIPTION</h2>
        <article className="text-sm text-gray-300">
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
            {job.description_markdown}
          </ReactMarkdown>
        </article>
        <p className="mt-4 border-t border-gray-800 pt-3 text-xs text-gray-600">
          Source may hold more detail than its API exposes —{" "}
          <a href={job.job_url} target="_blank" rel="noopener noreferrer"
             className="text-cyber-cyan underline">
            view the original posting ↗
          </a>
        </p>
      </section>

      {explanation && explanation.top_matches.length > 0 && (
        <section className="mt-6 border border-gray-800 bg-surface p-5">
          <h2 className="mb-2 text-sm font-bold tracking-widest text-gray-400">
            ▓ WHY THIS SCORE
          </h2>
          <ul className="space-y-2 text-xs text-gray-400">
            {explanation.top_matches.map((m, i) => (
              <li key={i} className="flex gap-3">
                <span className="shrink-0 font-bold text-cyber-cyan">
                  {m.similarity.toFixed(2)}
                </span>
                <span>“{m.phrase}”</span>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-[10px] text-gray-600">
            Top matching phrases from your candidate profile — edit the profile to tune ranking.
          </p>
        </section>
      )}

      <section className="mt-6 border border-gray-800 bg-surface p-5">
        <h2 className="mb-2 text-sm font-bold tracking-widest text-gray-400">▓ TIMELINE</h2>
        <div className="mb-3 flex gap-2">
          <input
            value={noteDraft}
            onChange={(e) => setNoteDraft(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submitNote()}
            placeholder="Add a note (contacts, referrals, interview details…)"
            className="min-w-0 flex-1 border border-gray-700 bg-void px-3 py-2 text-xs
                       text-gray-200 placeholder-gray-600 focus:border-cyber-cyan focus:outline-none"
          />
          <button
            onClick={submitNote}
            className="border border-cyber-cyan px-3 py-2 text-xs font-bold text-cyber-cyan
                       transition hover:bg-cyan-950"
          >
            SAVE
          </button>
        </div>
        {events.length === 0 ? (
          <p className="text-xs text-gray-600">No activity yet.</p>
        ) : (
          <ul className="space-y-2 text-xs">
            {events.map((e) => (
              <li key={e.id} className="flex gap-3 border-l-2 border-gray-800 pl-3">
                <span className="shrink-0 text-gray-600">
                  {new Date(e.created_at).toLocaleString()}
                </span>
                {e.event_type === "status" ? (
                  <span className="text-cyber-magenta">
                    → {e.status?.toUpperCase()}
                    {e.note && <span className="text-gray-400"> — {e.note}</span>}
                  </span>
                ) : (
                  <span className="text-gray-300">{e.note}</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {job.raw_metadata && Object.keys(job.raw_metadata).length > 0 && (
        <details className="mt-6 border border-gray-800 bg-surface p-5">
          <summary className="cursor-pointer text-sm font-bold tracking-widest text-gray-400">
            ▓ SOURCE METADATA ({Object.keys(job.raw_metadata).length} fields)
          </summary>
          <dl className="mt-3 space-y-1 text-xs">
            {Object.entries(job.raw_metadata).map(([k, v]) => (
              <div key={k} className="flex gap-2">
                <dt className="shrink-0 text-cyber-magenta">{k}:</dt>
                <dd className="break-all text-gray-400">
                  {typeof v === "object" ? JSON.stringify(v) : String(v)}
                </dd>
              </div>
            ))}
          </dl>
        </details>
      )}
    </main>
  );
}
