CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE repos (
    id SERIAL PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending', -- pending | ingesting | ready | error
    error_message TEXT,
    cloned_path TEXT,
    summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE files (
    id SERIAL PRIMARY KEY,
    repo_id INTEGER NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
    path TEXT NOT NULL,
    language TEXT,
    content_hash TEXT NOT NULL,
    summary TEXT,
    embedding_model TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (repo_id, path)
);

CREATE TABLE chunks (
    id SERIAL PRIMARY KEY,
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    repo_id INTEGER NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
    -- Denormalized copy of files.path: a generated column can only reference
    -- columns on its own table, and we want the file path itself searchable
    -- (both in full-text and in what gets embedded) so that a question which
    -- names a file directly actually retrieves that file's chunks.
    path TEXT NOT NULL DEFAULT '',
    symbol_name TEXT,
    symbol_type TEXT, -- function | class | method
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    code TEXT NOT NULL,
    docstring TEXT,
    embedding vector(384),
    -- Weighted so a literal filename/symbol match in the query ranks well
    -- above a chunk that merely happens to share a word with the code body.
    content_tsv tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(path, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(symbol_name, '')), 'B') ||
        setweight(to_tsvector('english', coalesce(docstring, '')), 'C') ||
        setweight(to_tsvector('english', coalesce(code, '')), 'D')
    ) STORED,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX chunks_repo_id_idx ON chunks (repo_id);
CREATE INDEX chunks_tsv_idx ON chunks USING GIN (content_tsv);
CREATE INDEX chunks_embedding_idx ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE TABLE static_findings (
    id SERIAL PRIMARY KEY,
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    repo_id INTEGER NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
    tool TEXT NOT NULL,
    severity TEXT,
    line INTEGER,
    message TEXT NOT NULL,
    rule_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX static_findings_file_id_idx ON static_findings (file_id);
CREATE INDEX static_findings_repo_id_idx ON static_findings (repo_id);
