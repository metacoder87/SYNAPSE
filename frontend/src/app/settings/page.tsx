"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { TOKEN_KEY, api, downloadExport } from "@/lib/api";

const FILES = [
  {
    name: "profile",
    label: "CANDIDATE PROFILE",
    hint: "Drives all matching — every job is scored against this text. Saving re-embeds automatically.",
  },
  {
    name: "resume",
    label: "MASTER RESUME",
    hint: "The tailor agent selects only from what's here. Keep it exhaustive and honest.",
  },
  {
    name: "filters",
    label: "FILTER RULES (YAML)",
    hint: "Kill-switch regexes. Validated before save; reloaded instantly.",
  },
] as const;

type FileName = (typeof FILES)[number]["name"];

export default function Settings() {
  const [contents, setContents] = useState<Record<string, string>>({});
  const [statuses, setStatuses] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const [token, setToken] = useState("");
  const [exportMsg, setExportMsg] = useState<string | null>(null);

  useEffect(() => {
    for (const f of FILES) {
      api
        .settingsFile(f.name)
        .then((r) => setContents((c) => ({ ...c, [f.name]: r.content })))
        .catch((e) =>
          setStatuses((s) => ({ ...s, [f.name]: `load failed: ${e}` }))
        );
    }
    try {
      setToken(localStorage.getItem(TOKEN_KEY) ?? "");
    } catch {}
  }, []);

  const save = async (name: FileName) => {
    setSaving(name);
    setStatuses((s) => ({ ...s, [name]: "" }));
    try {
      const r = await api.saveSettingsFile(name, contents[name] ?? "");
      setStatuses((s) => ({ ...s, [name]: `✓ ${r.status}` }));
    } catch (e) {
      setStatuses((s) => ({ ...s, [name]: `✗ ${e}` }));
    } finally {
      setSaving(null);
    }
  };

  const saveToken = () => {
    try {
      if (token.trim()) localStorage.setItem(TOKEN_KEY, token.trim());
      else localStorage.removeItem(TOKEN_KEY);
      setExportMsg("token saved locally");
    } catch {}
  };

  const doExport = async (path: string, filename: string) => {
    setExportMsg(`exporting ${filename}…`);
    try {
      await downloadExport(path, filename);
      setExportMsg(`✓ ${filename} downloaded`);
    } catch (e) {
      setExportMsg(`✗ export failed: ${e}`);
    }
  };

  return (
    <main className="mx-auto max-w-4xl p-6">
      <Link href="/" className="text-xs text-gray-500 hover:text-cyber-cyan">
        ← BACK TO QUEUE
      </Link>
      <h1 className="mt-4 text-2xl font-bold tracking-widest text-cyber-cyan">
        ⚙ SETTINGS
      </h1>

      {FILES.map((f) => (
        <section key={f.name} className="mt-6 border border-gray-800 bg-surface p-5">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-sm font-bold tracking-widest text-gray-300">
              ▓ {f.label}
            </h2>
            <button
              onClick={() => save(f.name)}
              disabled={saving === f.name}
              className="border border-cyber-cyan px-4 py-1 text-xs font-bold text-cyber-cyan
                         transition hover:bg-cyan-950 disabled:animate-pulse disabled:opacity-60"
            >
              {saving === f.name ? "SAVING…" : "SAVE"}
            </button>
          </div>
          <p className="mb-2 text-[11px] text-gray-600">{f.hint}</p>
          <textarea
            value={contents[f.name] ?? ""}
            onChange={(e) =>
              setContents((c) => ({ ...c, [f.name]: e.target.value }))
            }
            spellCheck={false}
            className="h-64 w-full resize-y border border-gray-700 bg-void p-3 font-mono
                       text-xs text-gray-200 focus:border-cyber-cyan focus:outline-none"
          />
          {statuses[f.name] && (
            <p
              className={`mt-1 text-xs ${
                statuses[f.name].startsWith("✓") ? "text-cyber-cyan" : "text-cyber-magenta"
              }`}
            >
              {statuses[f.name]}
            </p>
          )}
        </section>
      ))}

      <section className="mt-6 border border-gray-800 bg-surface p-5">
        <h2 className="mb-2 text-sm font-bold tracking-widest text-gray-300">▓ EXPORT</h2>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => doExport("/export/jobs.csv", "synapse_jobs.csv")}
            className="border border-cyber-cyan px-4 py-2 text-xs font-bold text-cyber-cyan
                       transition hover:bg-cyan-950"
          >
            ⬇ PIPELINE CSV
          </button>
          <button
            onClick={() => doExport("/export/backup.json", "synapse_backup.json")}
            className="border border-cyber-cyan px-4 py-2 text-xs font-bold text-cyber-cyan
                       transition hover:bg-cyan-950"
          >
            ⬇ FULL BACKUP (JSON)
          </button>
        </div>
        {exportMsg && <p className="mt-2 text-xs text-gray-400">{exportMsg}</p>}
      </section>

      <section className="mt-6 border border-gray-800 bg-surface p-5">
        <h2 className="mb-2 text-sm font-bold tracking-widest text-gray-300">▓ API TOKEN</h2>
        <p className="mb-2 text-[11px] text-gray-600">
          Only needed if AUTH_TOKEN is set in the backend .env (e.g. for LAN
          exposure). Stored in this browser only.
        </p>
        <div className="flex gap-2">
          <input
            type="password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="(empty = auth disabled)"
            className="min-w-0 flex-1 border border-gray-700 bg-void px-3 py-2 text-xs
                       text-gray-200 focus:border-cyber-cyan focus:outline-none"
          />
          <button
            onClick={saveToken}
            className="border border-cyber-cyan px-4 py-2 text-xs font-bold text-cyber-cyan
                       transition hover:bg-cyan-950"
          >
            SAVE TOKEN
          </button>
        </div>
      </section>
    </main>
  );
}
