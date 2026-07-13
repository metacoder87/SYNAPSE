import Link from "next/link";
import { Job, formatSalary } from "@/lib/api";

function scoreColor(score: number | null): string {
  if (score == null) return "text-gray-500 border-gray-600";
  if (score >= 0.5) return "text-cyber-cyan border-cyber-cyan shadow-glow-cyan";
  if (score >= 0.4) return "text-cyber-magenta border-cyber-magenta";
  return "text-gray-400 border-gray-600";
}

export default function JobCard({ job }: { job: Job }) {
  const salary = formatSalary(job);
  const closing = job.closing_date
    ? new Date(job.closing_date).toLocaleDateString()
    : null;

  return (
    <Link
      href={`/jobs/${job.id}`}
      data-testid="job-card"
      className="block border border-gray-800 bg-surface p-4 transition
                 hover:border-cyber-cyan hover:shadow-glow-cyan"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h2 className="truncate text-lg font-bold text-gray-100">{job.title}</h2>
          <p className="text-sm text-cyber-magenta">{job.company}</p>
          <p className="mt-1 text-xs text-gray-500">
            {job.location_string ?? "—"} · {job.source_provider}
          </p>
        </div>
        <div
          data-testid="score-badge"
          className={`shrink-0 border px-2 py-1 text-sm font-bold ${scoreColor(job.alignment_score)}`}
        >
          {job.alignment_score != null ? job.alignment_score.toFixed(3) : "N/A"}
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2 text-xs">
        {job.is_remote && (
          <span className="border border-cyber-cyan px-2 py-0.5 text-cyber-cyan">REMOTE</span>
        )}
        {salary && (
          <span className="border border-gray-600 px-2 py-0.5 text-gray-300">{salary}</span>
        )}
        {job.security_clearance && (
          <span className="border border-cyber-magenta px-2 py-0.5 text-cyber-magenta">
            🔒 {job.security_clearance}
          </span>
        )}
        {closing && (
          <span className="border border-gray-600 px-2 py-0.5 text-gray-400">
            CLOSES {closing}
          </span>
        )}
      </div>
    </Link>
  );
}
