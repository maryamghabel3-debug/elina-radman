-- Migration: durable carousel drafts (M29)
--
-- One row per owner chat. The draft JSONB holds the editable carousel
-- state (mode, template, topic, ordered image storage keys, ordered slide
-- texts, deck, rendered media keys, history of finalized versions) so a
-- carousel draft survives bot restarts and can be resumed later.
--
-- Idempotent and safe migration.

CREATE TABLE IF NOT EXISTS carousel_drafts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_chat_id bigint NOT NULL UNIQUE,
  title text NOT NULL DEFAULT '',
  custom_id text,
  status text NOT NULL DEFAULT 'draft',
  draft jsonb NOT NULL DEFAULT '{}'::jsonb,
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_carousel_drafts_updated_at
  ON carousel_drafts (updated_at DESC);
