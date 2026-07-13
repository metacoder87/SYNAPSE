"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, Dossier, Job, JobStatus, formatSalary } from "@/lib/api";
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
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    api.job(id).then(setJob).catch((e) => setError(String(e)));
    api.dossier(id).then(setDossier).catch(() => {});
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [id]);

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
              Company Scout → Networker → Fact-Checker…
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

      <section className="mt-6 border border-gray-800 bg-surface p-5">
        <h2 className="mb-2 text-sm font-bold tracking-widest text-gray-400">▓ JOB DESCRIPTION</h2>
        <article className="text-sm text-gray-300">
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
            {job.description_markdown}
          </ReactMarkdown>
        </article>
      </section>
    </main>
  );
}
