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

## The compass mark

`assets/compass-mark.png` (navy mark, transparent, 64px for 32px display).
Email clients do not render SVG or `data:` images reliably, so the templates
reference a hosted PNG at:

    https://signalnorthintel.com/email/compass-mark.png

Upload `assets/compass-mark.png` to that path before the first real send. Until
it is hosted, clients show the `alt="Signal North"` text — no broken layout.

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

- The domain is verified in Resend, so DKIM and SPF should already be in DNS.
  Confirm a **DMARC** record exists (`p=none` is enough to start); gov mail
  filters weight it, and these are the links the whole flow depends on.
- Send one of each to a seed address and check rendering in Outlook, Gmail and
  Apple Mail before enabling for real signups.
