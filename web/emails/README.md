# Signal North transactional + lifecycle emails

Claude Design's six-email set (export integrated 2026-08-03), replacing the
earlier hand-built template set. 600px column, text serif wordmark lockup +
3px navy rule masthead (no image — Outlook blocks remote images by default),
crimson bulletproof button, Outlook-safe tables. HTML + plain-text twin each.

**Nothing is wired.** These are files for operator approval; the send paths
(free double opt-in, Stripe welcome, Supabase templates) are built in G.

## The six

| File | Sent by | Link variable | CASL |
|------|---------|---------------|------|
| `01-confirm-subscription` | our code (Resend) — free double opt-in | `{{confirm_url}}` | commercial-list opt-in: unsubscribe + address |
| `02-free-welcome` | our code (Resend) — after 01 confirms | `{{welcome_cta_url}}` / `{{welcome_cta_label}}` | **commercial**: unsubscribe + address |
| `03-member-welcome` | our code (Stripe webhook) — post-payment | `{{signin_url}}` (generated magic link) | transactional service message, no unsubscribe |
| `04-sign-in-link` | **Supabase** → Magic Link | `{{ .SiteURL }}/auth/confirm?token_hash={{ .TokenHash }}&type=magiclink` | transactional |
| `05-password-reset` | **Supabase** → Reset Password | `…&type=recovery` | transactional |
| `06-email-change` | **Supabase** → Change Email Address | `…&type=email_change`; old address `{{ .Email }}` | transactional |

The `type` differs per Supabase template and must be exact — our
`app/auth/confirm/route.ts` calls `verifyOtp(token_hash, type)`, so a wrong
`type` produces a link that looks fine and verifies nothing.

Under change A there is **no Supabase "Confirm signup" email** — Weekly accounts
are provisioned by the webhook (`email_confirm: true`), so that template never
fires. The Supabase-bound templates are only 04 / 05 / 06.

## Open flags (operator decisions before send)

- **`{{business_address}}`** (01, 02): CASL requires a real registered mailing
  address in *commercial* messages. We have none until incorporation, so it is
  a flagged placeholder, not invented. **02-free-welcome legally needs it**
  (and so will the weekly brief); **01** is the commercial-list opt-in so it
  carries it too; **03–06 are transactional and do not need it** (address
  removed there). The entity name "Signal North Research Ltd." from the export
  was also removed as unverified — confirm the real registered name.
- **03 reference / amounts** were a hardcoded fake (`Reference 8842-QC`,
  `$3,900.00 paid 3 August 2026`). Now variables (`{{reference}}`, `{{amount}}`,
  `{{paid_date}}`, `{{renews_date}}`, `{{tier_line}}`) filled from real Stripe
  data at send — or drop the block entirely, since Stripe emails its own
  receipt. Operator's call.
- **02 CTA** (`{{welcome_cta_url}}` / `{{welcome_cta_label}}`): the export
  pointed at `/brief/latest` (the public sample brief, which does not exist
  until C). Until then it points at `/pricing` with label "See what Weekly
  includes"; re-point to the sample brief when C ships.

## Custom SMTP (Supabase → Resend), unchanged

Authentication → Emails → SMTP Settings → Custom SMTP:

| Field | Value |
|-------|-------|
| Sender email | `mail@signalnorthintel.com` |
| Sender name | `Signal North` |
| Host | `smtp.resend.com` |
| Port | `465` |
| Username | `resend` |
| Password | Resend API key (`re_…`) |

`mail@` is send-only; auth templates carry a footer pointing replies to
`giancarlo@signalnorthintel.com`. DKIM/SPF/DMARC are in DNS (`_dmarc` added
2026-08-03).
