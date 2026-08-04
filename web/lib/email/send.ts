// One place the server sends a transactional email through Resend. Reuses the
// exact call shape proven in app/brief/actions.ts (raw fetch, not the SDK, so
// there is no extra dependency and the failure surface is a plain Response).
//
// SERVER ONLY. RESEND_API_KEY is a Vercel runtime secret and never reaches a
// browser bundle; this module is imported only by route handlers and server
// actions. It is deliberately NOT wired into `node --test`: the callers own
// their own tests against the pure renderers, and this thin I/O wrapper is
// exercised by the real Stripe/Resend path in test mode.
//
// Every path returns a typed result rather than throwing, so a caller can log
// the exact reason a send failed (a paying member with no welcome, or an
// operator alarm that itself could not be delivered) instead of a swallowed
// exception.

export interface SendResult {
  ok: boolean;
  // Set when Resend was reached and answered. Absent on a network error or a
  // missing key, which the message distinguishes.
  status?: number;
  // Human-readable reason on failure; empty on success.
  message: string;
}

export interface SendInput {
  from: string;
  to: string[];
  subject: string;
  html: string;
  text: string;
  // Optional Reply-To, used by the operator alarm so a reply reaches the desk.
  replyTo?: string;
}

export async function sendEmail(input: SendInput): Promise<SendResult> {
  const key = process.env.RESEND_API_KEY;
  if (!key) {
    return {
      ok: false,
      message:
        "RESEND_API_KEY not visible to the server; email not sent. " +
        "(Vercel runtime secret; absent in CI/local and preview-only scopes.)",
    };
  }

  let resp: Response;
  try {
    resp = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${key}`,
        "content-type": "application/json",
      },
      body: JSON.stringify({
        from: input.from,
        to: input.to,
        subject: input.subject,
        html: input.html,
        text: input.text,
        ...(input.replyTo ? { reply_to: input.replyTo } : {}),
      }),
    });
  } catch (e) {
    return { ok: false, message: `Network error calling Resend: ${String(e).slice(0, 160)}` };
  }

  if (!resp.ok) {
    const body = await resp.text().catch(() => "");
    return {
      ok: false,
      status: resp.status,
      message: `Resend rejected the send (HTTP ${resp.status}): ${body.slice(0, 200)}`,
    };
  }
  return { ok: true, status: resp.status, message: "sent" };
}
