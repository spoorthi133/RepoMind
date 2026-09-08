export type RepoStatus = "pending" | "ingesting" | "ready" | "error";

export interface Repo {
  id: number;
  url: string;
  name: string;
  status: RepoStatus;
  error_message: string | null;
}

export interface Citation {
  file_path: string;
  start_line: number;
  end_line: number;
  symbol_name: string | null;
}

export interface Finding {
  file_path: string;
  tool: string;
  severity: string | null;
  line: number;
  message: string;
}

export interface FileSummary {
  path: string;
  summary: string;
}

export interface SummaryResponse {
  repo_summary: string | null;
  status: RepoStatus;
  files: FileSummary[];
}
