-- D1 Database Schema for Durable WhatsApp Capture Relay

-- 1. Sender Allowlist (only registered team/vendor numbers are accepted)
CREATE TABLE IF NOT EXISTS sender_allowlist (
    id TEXT PRIMARY KEY,
    phone_number TEXT UNIQUE NOT NULL,
    sender_name TEXT,
    role TEXT NOT NULL DEFAULT 'OPERATIONAL_STAFF',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 2. Inbound Messages
CREATE TABLE IF NOT EXISTS inbound_messages (
    id TEXT PRIMARY KEY,
    wamid TEXT UNIQUE NOT NULL,
    sender_phone TEXT NOT NULL,
    sender_name TEXT,
    caption TEXT,
    status TEXT NOT NULL DEFAULT 'PENDING_LOCAL', -- PENDING_LOCAL, LEASED, SYNCED, REJECTED
    received_at TEXT NOT NULL DEFAULT (datetime('now')),
    leased_at TEXT,
    lease_expires_at TEXT,
    synced_at TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0
);

-- 3. Inbound Media Attachments
CREATE TABLE IF NOT EXISTS inbound_media (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL REFERENCES inbound_messages(id) ON DELETE CASCADE,
    r2_key TEXT NOT NULL,
    file_name TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    sha256_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Indexes for efficient querying & dedup
CREATE INDEX IF NOT EXISTS idx_messages_wamid ON inbound_messages(wamid);
CREATE INDEX IF NOT EXISTS idx_messages_status ON inbound_messages(status);
CREATE INDEX IF NOT EXISTS idx_media_message_id ON inbound_media(message_id);
