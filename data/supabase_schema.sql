-- AutoTube Supabase Schema — pending_videos queue table
-- Run this SQL in Supabase SQL Editor to create the queue table for the two-job pipeline

CREATE TABLE IF NOT EXISTS pending_videos (
  id            SERIAL PRIMARY KEY,
  topic         TEXT NOT NULL,
  script_json   JSONB NOT NULL,
  image_cache   JSONB DEFAULT '{}',
  status        TEXT DEFAULT 'pending',   -- pending | rendering | published | failed
  approved      BOOLEAN DEFAULT true,      -- set false to skip without deleting
  created_at    TIMESTAMPTZ DEFAULT now(),
  published_at  TIMESTAMPTZ,
  youtube_url   TEXT,
  error_text    TEXT
);

-- Index for fast queue polling (critical for render job performance)
CREATE INDEX IF NOT EXISTS idx_pending_videos_status
  ON pending_videos(status, approved, created_at);

-- Enable RLS for service role access (used by GitHub Actions)
ALTER TABLE pending_videos ENABLE ROW LEVEL SECURITY;

-- Allow read/write for service role (ANON_KEY with unrestricted policy for GitHub Actions)
CREATE POLICY "service_rw" ON pending_videos
  USING (true)
  WITH CHECK (true);

-- Grant table access to authenticated and anonymous roles
GRANT ALL ON pending_videos TO authenticated, anon, service_role;
