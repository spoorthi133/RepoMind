import { useState } from "react";
import type { FormEvent } from "react";
import type { Repo } from "../types";
import { StatusBadge } from "./StatusBadge";

export function Sidebar({
  repos,
  selectedId,
  onSelect,
  onAdd,
  onRemove,
  adding,
  addError,
}: {
  repos: Repo[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  onAdd: (url: string) => void;
  onRemove: (id: number) => void;
  adding: boolean;
  addError: string | null;
}) {
  const [url, setUrl] = useState("");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = url.trim();
    if (!trimmed) return;
    onAdd(trimmed);
    setUrl("");
  }

  return (
    <aside className="sidebar">
      <h1 className="brand">RepoMind</h1>
      <form className="add-repo-form" onSubmit={handleSubmit}>
        <input
          type="text"
          placeholder="https://github.com/org/repo.git"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          disabled={adding}
        />
        <button type="submit" disabled={adding || !url.trim()}>
          {adding ? "Adding…" : "Add repo"}
        </button>
      </form>
      {addError && <p className="error">{addError}</p>}

      <nav className="repo-list">
        {repos.length === 0 && <p className="muted">No repos yet — add one above.</p>}
        {repos.map((repo) => (
          <div
            key={repo.id}
            className={`repo-item${repo.id === selectedId ? " selected" : ""}`}
            onClick={() => onSelect(repo.id)}
          >
            <div className="repo-item-main">
              <span className="repo-name">{repo.name}</span>
              <StatusBadge status={repo.status} />
            </div>
            <button
              className="icon-button"
              title="Remove from list"
              onClick={(e) => {
                e.stopPropagation();
                onRemove(repo.id);
              }}
            >
              ×
            </button>
          </div>
        ))}
      </nav>
    </aside>
  );
}
