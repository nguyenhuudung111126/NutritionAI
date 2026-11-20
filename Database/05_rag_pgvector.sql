-- =====================================================================
-- 05_rag_pgvector.sql - Kho tri thức RAG (hướng dẫn dinh dưỡng lâm sàng)
-- Yêu cầu: extension pgvector (https://github.com/pgvector/pgvector)
--   Windows: tải bản build cho PG18 hoặc dùng Docker image pgvector/pgvector:pg18
-- =====================================================================
CREATE EXTENSION IF NOT EXISTS vector;
SET search_path TO nutri, public;

CREATE TABLE knowledge_documents (
    id              SERIAL PRIMARY KEY,
    title           VARCHAR(300) NOT NULL,
    source          VARCHAR(300),                  -- "Bộ Y tế - QĐ 2879/2006", "KDIGO 2024"...
    group_name      VARCHAR(60),                   -- lọc theo nhóm bệnh (khớp conditions.group_name)
    published_year  SMALLINT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE knowledge_chunks (
    id              BIGSERIAL PRIMARY KEY,
    document_id     INTEGER NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    chunk_index     INTEGER NOT NULL,
    content         TEXT NOT NULL,
    metadata        JSONB DEFAULT '{}',
    embedding       vector(768),                   -- đổi số chiều theo model embedding
    UNIQUE (document_id, chunk_index)
);
CREATE INDEX idx_chunks_embedding ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);

-- Truy vấn mẫu (top-5 đoạn liên quan, lọc theo nhóm bệnh):
-- SELECT c.content, d.source, 1 - (c.embedding <=> $1) AS score
-- FROM knowledge_chunks c JOIN knowledge_documents d ON d.id = c.document_id
-- WHERE d.group_name = ANY($2)
-- ORDER BY c.embedding <=> $1 LIMIT 5;
