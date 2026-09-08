import type { RepoStatus } from "../types";

const LABELS: Record<RepoStatus, string> = {
  pending: "Queued",
  ingesting: "Ingesting…",
  ready: "Ready",
  error: "Error",
};

export function StatusBadge({ status }: { status: RepoStatus }) {
  return <span className={`status-badge status-${status}`}>{LABELS[status]}</span>;
}
