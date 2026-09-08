import { useState } from "react";
import type { FormEvent } from "react";
import { postSSE } from "../api/client";
import type { Citation } from "../types";
import { CitationList } from "./CitationList";
import { CodeModal } from "./CodeModal";

interface Message {
  role: "user" | "assistant";
  text: string;
  citations: Citation[];
}

export function ChatPanel({ repoId }: { repoId: number }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [openCitation, setOpenCitation] = useState<Citation | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const q = question.trim();
    if (!q || streaming) return;

    setMessages((prev) => [...prev, { role: "user", text: q, citations: [] }]);
    setQuestion("");
    setStreaming(true);

    const assistantIndex = messages.length + 1;
    setMessages((prev) => [...prev, { role: "assistant", text: "", citations: [] }]);

    try {
      for await (const evt of postSSE(`/repos/${repoId}/chat`, { question: q, k: 8 })) {
        if (evt.event === "citations") {
          const citations = JSON.parse(evt.data) as Citation[];
          setMessages((prev) => {
            const next = [...prev];
            next[assistantIndex] = { ...next[assistantIndex], citations };
            return next;
          });
        } else if (evt.event === "token") {
          const { text } = JSON.parse(evt.data) as { text: string };
          setMessages((prev) => {
            const next = [...prev];
            next[assistantIndex] = { ...next[assistantIndex], text: next[assistantIndex].text + text };
            return next;
          });
        } else if (evt.event === "done") {
          break;
        }
      }
    } catch (err) {
      setMessages((prev) => {
        const next = [...prev];
        next[assistantIndex] = {
          ...next[assistantIndex],
          text: next[assistantIndex].text || `Error: ${err instanceof Error ? err.message : String(err)}`,
        };
        return next;
      });
    } finally {
      setStreaming(false);
    }
  }

  return (
    <div className="panel chat-panel">
      <div className="messages">
        {messages.length === 0 && (
          <p className="muted">Ask a question about this repo — answers cite the exact lines they draw on.</p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`message message-${m.role}`}>
            <div className="message-role">{m.role === "user" ? "You" : "RepoMind"}</div>
            <div className="message-text">{m.text || (streaming && i === messages.length - 1 ? "…" : "")}</div>
            <CitationList citations={m.citations} onSelect={setOpenCitation} />
          </div>
        ))}
      </div>

      <form className="composer" onSubmit={handleSubmit}>
        <input
          type="text"
          placeholder="How does authentication work in this repo?"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={streaming}
        />
        <button type="submit" disabled={streaming || !question.trim()}>
          {streaming ? "Thinking…" : "Ask"}
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
