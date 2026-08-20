-- Migration: Add render output fields to content_items
-- Idempotent and safe migration

ALTER TABLE content_items
  ADD COLUMN IF NOT EXISTS edited_media_key text;

ALTER TABLE content_items
  ADD COLUMN IF NOT EXISTS edited_media_history jsonb NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE content_items
  ADD COLUMN IF NOT EXISTS last_rendered_at timestamptz;

ALTER TABLE content_items
  ADD COLUMN IF NOT EXISTS last_render_job_id text;
