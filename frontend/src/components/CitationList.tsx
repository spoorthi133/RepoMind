import type { Citation } from "../types";

export function CitationList({
  citations,
  onSelect,
}: {
  citations: Citation[];
  onSelect: (c: Citation) => void;
}) {
  if (citations.length === 0) return null;
  return (
    <div className="citations">
      {citations.map((c, i) => (
        <button
          key={`${c.file_path}:${c.start_line}-${c.end_line}:${i}`}
          className="citation-chip"
          onClick={() => onSelect(c)}
        >
          {c.file_path}:{c.start_line}-{c.end_line}
        </button>
      ))}
    </div>
  );
}
