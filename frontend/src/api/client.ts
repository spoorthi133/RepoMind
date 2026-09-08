import type { Repo, SummaryResponse } from "../types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api";

async function asJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json() as Promise<T>;
}

export function createRepo(url: string): Promise<Repo> {
  return fetch(`${API_BASE}/repos`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  }).then((res) => asJson<Repo>(res));
}

export function getRepo(id: number): Promise<Repo> {
  return fetch(`${API_BASE}/repos/${id}`).then((res) => asJson<Repo>(res));
}

export function getSummary(id: number): Promise<SummaryResponse> {
  return fetch(`${API_BASE}/repos/${id}/summary`).then((res) => asJson<SummaryResponse>(res));
}

export function getChunkSource(
  id: number,
  filePath: string,
  startLine: number,
  endLine: number,
): Promise<{ code: string }> {
  const params = new URLSearchParams({
    file_path: filePath,
    start_line: String(startLine),
    end_line: String(endLine),
  });
  return fetch(`${API_BASE}/repos/${id}/chunk?${params}`).then((res) => asJson<{ code: string }>(res));
}

export interface SSEEvent {
  event: string;
  data: string;
}

/** Parses a `text/event-stream` POST response into individual {event, data} messages. */
export async function* postSSE(
  path: string,
  body: unknown,
  signal?: AbortSignal,
): AsyncGenerator<SSEEvent> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let sepIndex: number;
    while ((sepIndex = buffer.indexOf("\n\n")) !== -1) {
      const rawBlock = buffer.slice(0, sepIndex);
      buffer = buffer.slice(sepIndex + 2);

      let event = "message";
      const dataLines: string[] = [];
      for (const line of rawBlock.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
      }
      if (dataLines.length > 0) {
        yield { event, data: dataLines.join("\n") };
      }
    }
  }
}
