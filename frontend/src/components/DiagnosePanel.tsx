import { useState } from "react";
import type { FormEvent } from "react";
import { postSSE } from "../api/client";
import type { Citation, Finding } from "../types";
import { CitationList } from "./CitationList";
import { CodeModal } from "./CodeModal";

interface Result {
  errorText: string;
  answer: string;
  citations: Citation[];
  findings: Finding[];
}

export function DiagnosePanel({ repoId }: { repoId: number }) {
  const [errorText, setErrorText] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [results, setResults] = useState<Result[]>([]);
  const [openCitation, setOpenCitation] = useState<Citation | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const text = errorText.trim();
    if (!text || streaming) return;

    setStreaming(true);
    const index = results.length;
    setResults((prev) => [...prev, { errorText: text, answer: "", citations: [], findings: [] }]);
    setErrorText("");

    try {
      for await (const evt of postSSE(`/repos/${repoId}/diagnose`, { error_text: text, k: 6 })) {
        if (evt.event === "citations") {
          const citations = JSON.parse(evt.data) as Citation[];
          setResults((prev) => {
            const next = [...prev];
            next[index] = { ...next[index], citations };
            return next;
          });
        } else if (evt.event === "findings") {
          const findings = JSON.parse(evt.data) as Finding[];
          setResults((prev) => {
            const next = [...prev];
            next[index] = { ...next[index], findings };
            return next;
          });
        } else if (evt.event === "token") {
          const { text: token } = JSON.parse(evt.data) as { text: string };
          setResults((prev) => {
            const next = [...prev];
            next[index] = { ...next[index], answer: next[index].answer + token };
            return next;
          });
        } else if (evt.event === "done") {
          break;
        }
      }
    } catch (err) {
      setResults((prev) => {
        const next = [...prev];
        next[index] = {
          ...next[index],
          answer: next[index].answer || `Error: ${err instanceof Error ? err.message : String(err)}`,
        };
        return next;
      });
    } finally {
      setStreaming(false);
    }
  }

  return (
    <div className="panel diagnose-panel">
      <div className="messages">
        {results.length === 0 && (
          <p className="muted">Paste a stack trace or error message — RepoMind will ground its reasoning in retrieved code and static analysis findings.</p>
        )}
        {results.map((r, i) => (
          <div key={i} className="diagnose-result">
            <pre className="error-input">{r.errorText}</pre>

            {r.findings.length > 0 && (
              <div className="findings">
                <div className="findings-title">Linked static analysis findings</div>
                {r.findings.map((f, j) => (
                  <div key={j} className={`finding finding-${(f.severity ?? "unknown").toLowerCase()}`}>
                    <span className="finding-tool">{f.tool}</span>
                    <span className="mono">
                      {f.file_path}:{f.line}
                    </span>
                    <span>{f.message}</span>
                  </div>
                ))}
              </div>
            )}

            <div className="message message-assistant">
              <div className="message-role">RepoMind</div>
              <div className="message-text">{r.answer || (streaming && i === results.length - 1 ? "…" : "")}</div>
              <CitationList citations={r.citations} onSelect={setOpenCitation} />
            </div>
          </div>
        ))}
      </div>

      <form className="composer" onSubmit={handleSubmit}>
        <textarea
          placeholder="Paste the error text or stack trace…"
          value={errorText}
          onChange={(e) => setErrorText(e.target.value)}
          disabled={streaming}
          rows={3}
        />
        <button type="submit" disabled={streaming || !errorText.trim()}>
          {streaming ? "Diagnosing…" : "Diagnose"}
        </button>
      </form>

      {openCitation && (
        <CodeModal
          key={`${openCitation.file_path}:${openCitation.start_line}-${openCitation.end_line}`}
          repoId={repoId}
          citation={openCitation}
          onClose={() => setOpenCitation(null)}
        />
      )}
    </div>
  );
}
