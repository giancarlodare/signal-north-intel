# $1 live-price validation runbook

Operator go: 2026-08-04. The one live-mode rehearsal before launch: prove the
checkout-first chain end to end with real money at $1, then put everything back
to test configuration. The walkthrough in chat follows this document step by
step; this is the durable copy.

**Principles.** The site stays dark throughout (only an authenticated session
reaches /join, so no member of the public can stumble into the $1 price). The
validation exercises the NORMAL flow -- the trick is only that
`STRIPE_PRICE_WEEKLY_ANNUAL` points at a temporary $1 recurring price, so
nothing bespoke runs. Real card, real charge, refunded at the end.

## How STRIPE_LIVE_APPROVED works (read before touching env)

`lib/billing/config.ts` `keyRefusalReason()`:

* a `sk_test_`/`rk_test_` key is always accepted;
* ANY other key (i.e. live) is REFUSED unless `STRIPE_LIVE_APPROVED === "true"`.

A refused key makes `billingConfig()` return `null`, which turns billing
entirely dark: checkout buttons dead-end honestly, and the webhook answers 503
to everything. Two consequences:

1. Staging `sk_live_...` into Vercel WITHOUT the flag does not enable live
   charges -- it just darkens billing until the flag flips. The flag is the
   deliberate go-live act, separate from possessing the key.
2. There is ONE `STRIPE_SECRET_KEY` per environment, so live and test cannot
   run concurrently in Production. The validation swaps Production to live for
   a short window, then swaps back. While swapped, the TEST flow is dark (by
   construction, not by accident).

## Steps

1. **Stripe account activation.** Live payments require the activated account
   (business profile, bank account for payouts, CAD). Dashboard -> Activate
   payments. Without this, live keys exist but charges are refused.
2. **Create the live catalog** (Dashboard in LIVE mode -> Product catalog):
   one product "Signal North Weekly" with recurring prices $3,900/year and
   $390/month CAD; one product "Signal North Pro" with $19,000/year and
   $1,900/month CAD (created now so launch is env-only; nothing points at them
   until the env does). Plus the TEMPORARY validation price on the Weekly
   product: **$1.00 CAD, recurring, yearly** -- it must be recurring, because
   the checkout session is created in subscription mode and a one-time price
   would be refused. Record all five price ids.
3. **Register the live webhook endpoint** (Developers -> Webhooks, LIVE mode):
   `https://signalnorthintel.com/api/stripe/webhook`, events
   `checkout.session.completed`, `customer.subscription.created`,
   `customer.subscription.updated`, `customer.subscription.deleted`. Record its
   signing secret (`whsec_...`). Live and test endpoints coexist; each has its
   own secret.
4. **Stage Vercel Production env** (note the current test values first so the
   revert is mechanical): set `STRIPE_SECRET_KEY` = live secret key,
   `STRIPE_WEBHOOK_SECRET` = the live endpoint's signing secret,
   `STRIPE_PRICE_WEEKLY_ANNUAL` = the **$1 price id**,
   `STRIPE_PRICE_WEEKLY_MONTHLY` = live $390 price id (unused in the test),
   `MEMBER_WELCOME_LIVE=true`, and LAST, `STRIPE_LIVE_APPROVED=true`.
   Redeploy. The order matters only in that the flag is the arming step.
5. **The $1 checkout.** Signed in (any authenticated session passes the dark
   gate), /join -> Annual -> real card, a FRESH inbox address typed into
   Checkout (e.g. `+live1`). Live mode refuses 4242: real card only.
6. **Verify every link of the chain:** (a) Stripe shows the $1 charge and an
   ACTIVE subscription on the $1 price; (b) the live endpoint's delivery log
   shows `checkout.session.completed` -> HTTP 200; (c) `diag_checkout` for the
   address shows the auth user + `member_subscriptions` row
   (weekly/annual/active) and no failure row; (d) the welcome arrived at the
   address, dated Monday line correct; (e) its sign-in link lands in the
   portal: /portal redirects to /portal/brief (paid). Any red stops here and
   gets diagnosed before the revert.
7. **Refund and archive.** Dashboard: refund the $1 payment; cancel the
   subscription; archive the $1 price (never delete a price with history).
   Supabase side: `cleanup-member` for the `+live1` address (its Stripe half
   no-ops under a test key; the dashboard already did the live half).
8. **Revert to test configuration:** `STRIPE_LIVE_APPROVED=false` FIRST (dis-
   arms), then restore `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, and the
   two price ids to their test values; `MEMBER_WELCOME_LIVE` back to the
   operator's preferred state. Redeploy. Launch later becomes: repoint the two
   price env vars at the real live prices, swap key + webhook secret, flip
   `STRIPE_LIVE_APPROVED=true` -- no code.

## What this proves that test mode could not

Live-mode account activation, the live webhook endpoint + secret, live email
deliverability of the welcome, and the full money path (charge, payout ledger,
refund) -- the only parts of the chain test mode structurally cannot touch.
