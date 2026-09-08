import { useEffect, useState } from "react";
import { getSummary } from "../api/client";
import type { SummaryResponse } from "../types";

export function SummaryPanel({ repoId }: { repoId: number }) {
  const [summary, setSummary] = useState<SummaryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [openFile, setOpenFile] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setSummary(null);
    setError(null);
    getSummary(repoId)
      .then((res) => {
        if (!cancelled) setSummary(res);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      cancelled = true;
    };
  }, [repoId]);

  if (error) return <p className="error">{error}</p>;
  if (!summary) return <p className="muted">Loading summary…</p>;

  return (
    <div className="panel summary-panel">
      {summary.repo_summary && <p className="repo-summary">{summary.repo_summary}</p>}
      {!summary.repo_summary && <p className="muted">No repo-level summary available yet.</p>}

      <h2 className="section-title">Files ({summary.files.length})</h2>
      <div className="file-list">
        {summary.files.map((f) => (
          <div key={f.path} className="file-item">
            <button className="file-path" onClick={() => setOpenFile(openFile === f.path ? null : f.path)}>
              {f.path}
            </button>
            {openFile === f.path && <p className="file-summary">{f.summary}</p>}
          </div>
        ))}
        {summary.files.length === 0 && <p className="muted">No per-file summaries available.</p>}
      </div>
    </div>
  );
}
