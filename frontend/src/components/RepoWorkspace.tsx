import { useState } from "react";
import type { Repo } from "../types";
import { ChatPanel } from "./ChatPanel";
import { DiagnosePanel } from "./DiagnosePanel";
import { SummaryPanel } from "./SummaryPanel";

type Tab = "chat" | "diagnose" | "summary";

export function RepoWorkspace({ repo }: { repo: Repo }) {
  const [tab, setTab] = useState<Tab>("chat");

  if (repo.status === "pending" || repo.status === "ingesting") {
    return (
      <div className="workspace-status">
        <p className="muted">Ingesting {repo.name}… this clones the repo, chunks it, and builds embeddings.</p>
      </div>
    );
  }

  if (repo.status === "error") {
    return (
      <div className="workspace-status">
        <p className="error">Failed to ingest {repo.name}: {repo.error_message ?? "unknown error"}</p>
      </div>
    );
  }

  return (
    <div className="workspace">
      <div className="tabs">
        <button className={tab === "chat" ? "active" : ""} onClick={() => setTab("chat")}>
          Chat
        </button>
        <button className={tab === "diagnose" ? "active" : ""} onClick={() => setTab("diagnose")}>
          Diagnose
        </button>
        <button className={tab === "summary" ? "active" : ""} onClick={() => setTab("summary")}>
          Summary
        </button>
      </div>
      {tab === "chat" && <ChatPanel key={repo.id} repoId={repo.id} />}
      {tab === "diagnose" && <DiagnosePanel key={repo.id} repoId={repo.id} />}
      {tab === "summary" && <SummaryPanel key={repo.id} repoId={repo.id} />}
    </div>
  );
}
