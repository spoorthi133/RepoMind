import { useEffect, useState } from "react";
import { getChunkSource } from "../api/client";
import type { Citation } from "../types";

export function CodeModal({
  repoId,
  citation,
  onClose,
}: {
  repoId: number;
  citation: Citation;
  onClose: () => void;
}) {
  const [code, setCode] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setCode(null);
    setError(null);
    getChunkSource(repoId, citation.file_path, citation.start_line, citation.end_line)
      .then((res) => {
        if (!cancelled) setCode(res.code);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      cancelled = true;
    };
  }, [repoId, citation]);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <span className="mono">
            {citation.file_path}:{citation.start_line}-{citation.end_line}
            {citation.symbol_name ? ` (${citation.symbol_name})` : ""}
          </span>
          <button className="icon-button" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <div className="modal-body">
          {error && <p className="error">{error}</p>}
          {!error && code === null && <p className="muted">Loading…</p>}
          {code !== null && <pre className="code-block">{code}</pre>}
        </div>
      </div>
    </div>
  );
}
