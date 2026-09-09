-- Run this once in the Supabase SQL editor (Project > SQL Editor > New query)

-- 1. Enable the pgvector extension
create extension if not exists vector;

-- 2. Table storing each memo (voice-transcribed or typed) with its embedding
-- 384 = output dimension of the "all-MiniLM-L6-v2" embedding model used in embeddings.py
create table if not exists memories (
  id bigserial primary key,
  content text not null,
  source text not null default 'text',   -- 'voice' or 'text'
  embedding vector(384) not null,
  created_at timestamptz not null default now()
);

-- 3. Index for fast approximate nearest-neighbor search
create index if not exists memories_embedding_idx
  on memories using hnsw (embedding vector_cosine_ops);

-- 4. Semantic search function, called via Supabase RPC from db.py
create or replace function match_memories(
  query_embedding vector(384),
  match_count int default 5
)
returns table (
  id bigint,
  content text,
  source text,
  created_at timestamptz,
  similarity float
)
language sql stable
as $$
  select
    id,
    content,
    source,
    created_at,
    1 - (embedding <=> query_embedding) as similarity
  from memories
  order by embedding <=> query_embedding
  limit match_count;
$$;

-- 5. Small key/value table used only by the GitHub Actions one-shot poller
-- (poll_once.py), to remember the last processed Telegram update_id across
-- separate, stateless job runs.
create table if not exists bot_state (
  key text primary key,
  value text not null
);

-- RLS is enabled by default when you create this table through the SQL
-- editor dialog. That's expected and fine — the bot connects with the
-- service_role key, which bypasses RLS entirely, so no policies are needed.
