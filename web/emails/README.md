# Signal North transactional emails

One shared template (off-white column ~480px, compass mark, serif heading, one
crimson table-based button, hairline, muted footer; table-based so it survives
Outlook, no web fonts, no imagery beyond the hosted mark). Every send has an
HTML file and a plain-text `.txt` alternative — pair them, never send HTML
alone.

| File | Where it goes | Link variable |
|------|---------------|---------------|
| `confirm-signup.*` | Supabase Auth → Email Templates → **Confirm signup** | `{{ .ConfirmationURL }}` |
| `magic-link.*` | Supabase Auth → Email Templates → **Magic Link** | `{{ .ConfirmationURL }}` |
| `reset-password.*` | Supabase Auth → Email Templates → **Reset Password** | `{{ .ConfirmationURL }}` |
| `change-email.*` | Supabase Auth → Email Templates → **Change Email Address** | `{{ .ConfirmationURL }}` |
| `confirm-subscription.*` | **Our code (Resend)**, free-brief double opt-in | `{{confirm_url}}` (filled by the send path) |

`confirm-subscription` is NOT a Supabase template — the free brief has no
`auth.users` row, so its confirm email is sent by our own code through Resend.
Its copy is DRAFTED (2026-08-03), pending operator approval; the other four use
copy already approved in `docs/auth-email-templates.md`. The send path itself
(capture → send confirm → confirm endpoint → add to list) is a separate build,
not yet wired.

## No images: text lockup by design

The header is a **text-only serif "Signal North" lockup**, not an image.
Remote images are blocked by default in a large share of clients (Outlook, many
Gmail configs), so a hosted mark would be absent on first open for many
recipients — and a missing image in the first email we ever send is worse than
no image. The text lockup always renders. There is nothing to host.

## Reply handling

`mail@signalnorthintel.com` is send-only. Supabase's auth email UI does not
expose a per-template Reply-To, so instead every template's footer states
plainly that the address is not monitored and points to
`giancarlo@signalnorthintel.com` (the monitored contact used across the site).
For `confirm-subscription` (sent by our own code via Resend), also set the
`Reply-To` header to that address when the send path is built.

## Custom SMTP: point Supabase at Resend

Supabase Dashboard → your project → **Authentication → Emails → SMTP Settings**
→ enable **Custom SMTP**, then fill:

| Field | Value |
|-------|-------|
| Sender email | `mail@signalnorthintel.com` (the address on the Resend-verified domain) |
| Sender name | `Signal North` |
| Host | `smtp.resend.com` |
| Port | `465` |
| Username | `resend` |
| Password | your Resend API key (`re_…`) |

Save, then paste each HTML file into its template under **Authentication →
Email Templates**, and set the subjects:

- Confirm signup — `Confirm your email to join Signal North`
- Magic Link — `Your Signal North sign-in link`
- Reset Password — `Reset your Signal North password`
- Change Email Address — `Confirm your new email address`

## Before the first real send

- DKIM, SPF and DMARC are all in DNS (DMARC `_dmarc` TXT added 2026-08-03).
- Send one of each to a seed address and check rendering in Outlook, Gmail and
  Apple Mail before enabling for real signups.
