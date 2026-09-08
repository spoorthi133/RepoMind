import { useCallback, useEffect, useState } from "react";
import { createRepo, getRepo } from "../api/client";
import type { Repo } from "../types";

const STORAGE_KEY = "repomind.repos";

function loadStoredRepos(): Repo[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Repo[]) : [];
  } catch {
    return [];
  }
}

export function useRepos() {
  const [repos, setRepos] = useState<Repo[]>(loadStoredRepos);
  const [selectedId, setSelectedId] = useState<number | null>(() => repos[0]?.id ?? null);
  const [addError, setAddError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(repos));
  }, [repos]);

  const upsertRepo = useCallback((repo: Repo) => {
    setRepos((prev) => {
      const idx = prev.findIndex((r) => r.id === repo.id);
      if (idx === -1) return [repo, ...prev];
      const next = [...prev];
      next[idx] = repo;
      return next;
    });
  }, []);

  const addRepo = useCallback(
    async (url: string) => {
      setAdding(true);
      setAddError(null);
      try {
        const repo = await createRepo(url);
        upsertRepo(repo);
        setSelectedId(repo.id);
      } catch (err) {
        setAddError(err instanceof Error ? err.message : String(err));
      } finally {
        setAdding(false);
      }
    },
    [upsertRepo],
  );

  const removeRepo = useCallback(
    (id: number) => {
      setRepos((prev) => prev.filter((r) => r.id !== id));
      setSelectedId((prev) => (prev === id ? null : prev));
    },
    [],
  );

  // Poll status for any repo still ingesting. Re-armed whenever `repos` changes so the
  // pending list stays current without needing a ref.
  const pendingIds = repos
    .filter((r) => r.status === "pending" || r.status === "ingesting")
    .map((r) => r.id)
    .join(",");
  useEffect(() => {
    if (!pendingIds) return;
    const interval = setInterval(async () => {
      for (const id of pendingIds.split(",").map(Number)) {
        try {
          const fresh = await getRepo(id);
          upsertRepo(fresh);
        } catch {
          // repo may have been deleted server-side; leave as-is
        }
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [pendingIds, upsertRepo]);

  const selectedRepo = repos.find((r) => r.id === selectedId) ?? null;

  return { repos, selectedRepo, selectedId, setSelectedId, addRepo, removeRepo, adding, addError };
}
