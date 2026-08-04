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

## CASL address (operator update 2026-08-03: solved, no incorporation dependency)

CASL requires a physical mailing address on every **commercial** electronic
message. The mailing address is **confirmed** — a Richmond Hill coworking
location. What remains is a ~$60 online **Ontario business-name registration**
so "Signal North" is a legally identifiable sender; there is **no dependency on
incorporation** for this. `{{business_address}}` stays a flagged variable
(filled from the confirmed address at send), and the entity name is never
invented.

So the free path is **not** blocked by a second address dependency — it is
gated by the **ethics gate like everything else**. The build structure still
holds: **capture and confirm ship independently of the welcome**, so the front
half can go live as soon as the ethics gate and the (small) name registration
clear, and only 02 waits on nothing more than that. The weekly intelligence
brief (#57) sits behind the same single gate, not a separate one.

## Other flags

- **03 payment block: dropped** (operator 2026-08-03). Stripe emails its own
  receipt under change A; two receipts for one payment is confusing and a
  reference number we must get right is risk with no upside. The welcome
  welcomes; Stripe handles the accounting. `{{first_brief_date}}` (the upcoming
  Monday from the purchase date) is filled at send.
- **02 CTA** (`{{welcome_cta_url}}` / `{{welcome_cta_label}}`): the export
  pointed at `/brief/latest` (the public sample brief, which does not exist
  until C). Until then it points at `/pricing` with label "See what Weekly
  includes"; re-point to the sample brief when C ships.

Brand consistency: **"public safety"** never hyphenated (matches the site);
the brief is the **"intelligence brief"**.

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
