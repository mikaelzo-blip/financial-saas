export interface Env {
  DB: D1Database;
  MEDIA_BUCKET: R2Bucket;
  ENVIRONMENT?: string;
  RELAY_API_KEY?: string;
  WHATSAPP_VERIFY_TOKEN?: string;
  MAX_MEDIA_SIZE_BYTES?: string;
  LEASE_TIMEOUT_SECONDS?: string;
}

interface WebhookPayload {
  object?: string;
  entry?: Array<{
    id?: string;
    changes?: Array<{
      value?: {
        messaging_product?: string;
        metadata?: { display_phone_number?: string; phone_number_id?: string };
        contacts?: Array<{ profile?: { name?: string }; wa_id?: string }>;
        messages?: Array<{
          from?: string;
          id?: string;
          timestamp?: string;
          type?: string;
          text?: { body?: string };
          image?: { id?: string; mime_type?: string; sha256?: string; caption?: string };
          document?: { id?: string; filename?: string; mime_type?: string; sha256?: string; caption?: string };
        }>;
      };
      field?: string;
    }>;
  }>;
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);
    const pathname = url.pathname;

    // 1. Health check
    if (pathname === '/health' && request.method === 'GET') {
      return new Response(JSON.stringify({ status: 'ok', service: 'financial-saas-edge-relay' }), {
        headers: { 'Content-Type': 'application/json' },
      });
    }

    // 2. WhatsApp Webhook verification (Meta standard)
    if (pathname === '/webhook/whatsapp' && request.method === 'GET') {
      const mode = url.searchParams.get('hub.mode');
      const token = url.searchParams.get('hub.verify_token');
      const challenge = url.searchParams.get('hub.challenge');

      const expectedToken = env.WHATSAPP_VERIFY_TOKEN || 'financial-saas-wa-token';
      if (mode === 'subscribe' && token === expectedToken) {
        return new Response(challenge || '', { status: 200 });
      }
      return new Response('Forbidden', { status: 403 });
    }

    // 3. Inbound WhatsApp webhook capture
    if (pathname === '/webhook/whatsapp' && request.method === 'POST') {
      try {
        const body: WebhookPayload = await request.json();
        return await handleInboundWebhook(body, env);
      } catch (err: any) {
        return new Response(JSON.stringify({ error: err.message }), {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        });
      }
    }

    // Authenticated endpoints for Local Finance PC Client
    const authHeader = request.headers.get('Authorization');
    const expectedKey = env.RELAY_API_KEY || 'dev-relay-secret';
    if (!authHeader || authHeader !== `Bearer ${expectedKey}`) {
      return new Response(JSON.stringify({ error: 'Unauthorized' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    // 4. Pull pending captures (with lease locking)
    if (pathname === '/api/v1/remote-inbox/pull' && request.method === 'GET') {
      const limit = parseInt(url.searchParams.get('limit') || '10', 10);
      return await handlePullPending(limit, env);
    }

    // 5. Acknowledge synced captures
    if (pathname === '/api/v1/remote-inbox/ack' && request.method === 'POST') {
      const body = await request.json();
      return await handleAck(body, env);
    }

    // 6. Download media from R2
    if (pathname.startsWith('/api/v1/remote-inbox/media/') && request.method === 'GET') {
      const key = pathname.replace('/api/v1/remote-inbox/media/', '');
      return await handleGetMedia(key, env);
    }

    return new Response('Not Found', { status: 404 });
  },
};

async function handleInboundWebhook(body: WebhookPayload, env: Env): Promise<Response> {
  const entries = body.entry || [];
  let capturedCount = 0;

  for (const entry of entries) {
    const changes = entry.changes || [];
    for (const change of changes) {
      const messages = change.value?.messages || [];
      const contacts = change.value?.contacts || [];
      const contactMap: Record<string, string> = {};
      for (const c of contacts) {
        if (c.wa_id && c.profile?.name) contactMap[c.wa_id] = c.profile.name;
      }

      for (const msg of messages) {
        const wamid = msg.id;
        const from = msg.from;
        if (!wamid || !from) continue;

        // Check sender allowlist
        const allowlistEntry = await env.DB.prepare(
          'SELECT is_active FROM sender_allowlist WHERE phone_number = ?'
        )
          .bind(from)
          .first<{ is_active: number }>();

        // If allowlist is active and sender not in allowlist or inactive, reject
        if (allowlistEntry !== null && allowlistEntry?.is_active !== 1) {
          continue; // Rejected sender
        }

        // Check WAMID idempotency
        const existing = await env.DB.prepare(
          'SELECT id FROM inbound_messages WHERE wamid = ?'
        )
          .bind(wamid)
          .first();

        if (existing) {
          continue; // Already captured
        }

        const msgId = crypto.randomUUID();
        const senderName = contactMap[from] || from;
        const caption =
          msg.text?.body ||
          msg.image?.caption ||
          msg.document?.caption ||
          '';

        await env.DB.prepare(
          `INSERT INTO inbound_messages (id, wamid, sender_phone, sender_name, caption, status)
           VALUES (?, ?, ?, ?, ?, 'PENDING_LOCAL')`
        )
          .bind(msgId, wamid, from, senderName, caption)
          .run();

        capturedCount++;
      }
    }
  }

  return new Response(JSON.stringify({ status: 'ok', captured: capturedCount }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
}

async function handlePullPending(limit: number, env: Env): Promise<Response> {
  const leaseSec = parseInt(env.LEASE_TIMEOUT_SECONDS || '300', 10);
  const now = new Date();
  const leaseExpires = new Date(now.getTime() + leaseSec * 1000).toISOString();
  const nowIso = now.toISOString();

  // Find messages that are PENDING_LOCAL or expired LEASED
  const { results: messages } = await env.DB.prepare(
    `SELECT id, wamid, sender_phone, sender_name, caption, received_at, retry_count
     FROM inbound_messages
     WHERE status = 'PENDING_LOCAL' OR (status = 'LEASED' AND lease_expires_at < ?)
     ORDER BY received_at ASC
     LIMIT ?`
  )
    .bind(nowIso, limit)
    .all();

  if (!messages || messages.length === 0) {
    return new Response(JSON.stringify({ items: [] }), {
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const items = [];
  for (const m of messages as any[]) {
    // Acquire lease
    await env.DB.prepare(
      `UPDATE inbound_messages
       SET status = 'LEASED', leased_at = ?, lease_expires_at = ?, retry_count = retry_count + 1
       WHERE id = ?`
    )
      .bind(nowIso, leaseExpires, m.id)
      .run();

    // Fetch media attachments
    const { results: media } = await env.DB.prepare(
      `SELECT id, r2_key, file_name, mime_type, size_bytes, sha256_hash
       FROM inbound_media
       WHERE message_id = ?`
    )
      .bind(m.id)
      .all();

    items.push({
      ...m,
      attachments: media || [],
    });
  }

  return new Response(JSON.stringify({ items }), {
    headers: { 'Content-Type': 'application/json' },
  });
}

async function handleAck(body: any, env: Env): Promise<Response> {
  const messageIds: string[] = body.message_ids || [];
  if (messageIds.length === 0) {
    return new Response(JSON.stringify({ acknowledged: 0 }), {
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const nowIso = new Date().toISOString();
  let count = 0;
  for (const id of messageIds) {
    const res = await env.DB.prepare(
      `UPDATE inbound_messages
       SET status = 'SYNCED', synced_at = ?
       WHERE id = ?`
    )
      .bind(nowIso, id)
      .run();
    if (res.meta.changes > 0) count++;
  }

  return new Response(JSON.stringify({ acknowledged: count }), {
    headers: { 'Content-Type': 'application/json' },
  });
}

async function handleGetMedia(r2Key: string, env: Env): Promise<Response> {
  const object = await env.MEDIA_BUCKET.get(r2Key);
  if (!object) {
    return new Response('Media Not Found', { status: 404 });
  }

  const headers = new Headers();
  object.writeHttpMetadata(headers);
  headers.set('etag', object.httpEtag);

  return new Response(object.body, { headers });
}
