# Signal Review (private internal tool)

A mobile-first, password-protected page for reviewing extracted signals — approve,
reject, and see which ones need organization resolution. **Private tool, not a
public product.** No landing page, no marketing, no subscription anything; a
`noindex` header + meta on every route. It stays private until the ethics gate
clears, at which point this same stack becomes the subscriber dashboard.

Stack: Next.js 14 (App Router) + Supabase Auth. Data protection is enforced in
the database with Row-Level Security, so the public Vercel URL yields nothing
without a login.

## Prerequisites (run once, in order)

1. **Apply the schema migrations** in the repo `migrations/` folder, in the
   Supabase SQL editor:
   - `2026-07-09_signals_unresolved_org.sql` (adds the columns this UI reads)
   - `2026-07-09_signals_rls_review.sql` (**the security layer — required**)
2. **Create your login user:** Supabase dashboard → **Authentication → Users →
   Add user** → enter your email + a strong password → **Create user**. (That's
   the only account; there is no public sign-up.)
3. **Get your keys:** Supabase dashboard → **Project Settings → API** → copy the
   **Project URL** and the **anon / publishable** key. **Do NOT use the
   service_role key here.**

## Run locally (optional, to try before deploying)

```bash
cd web
cp .env.example .env.local        # then fill in the two values
npm install
npm run dev                        # open http://localhost:3000
```

## Deploy to Vercel — click by click (first-timer)

You'll do this from the Vercel website. The repo already contains everything.

1. Go to **https://vercel.com** and click **Sign Up** → **Continue with GitHub**.
   Authorize Vercel to see your `giancarlodare/signal-north-intel` repo.
2. On the dashboard, click **Add New… → Project**.
3. Find **signal-north-intel** in the list and click **Import**.
4. **Root Directory:** click **Edit** next to it and choose **`web`**. ← important,
   because the Next.js app lives in the `web/` subfolder, not the repo root.
   (Framework Preset should auto-detect **Next.js**. Leave Build/Output settings
   at their defaults.)
5. Expand **Environment Variables** and add these two (from the prerequisites):
   - Name `NEXT_PUBLIC_SUPABASE_URL`  → Value: your Project URL
   - Name `NEXT_PUBLIC_SUPABASE_ANON_KEY` → Value: your anon/publishable key
   Leave every environment (Production/Preview/Development) checked.
6. Click **Deploy**. Wait ~1–2 minutes for the build to finish.
7. Click the deployment, then **Visit** (or **Continue to Dashboard → Domains**)
   to get your URL, e.g. `https://signal-north-intel-xxxx.vercel.app`.
8. Open that URL on your **phone**. You should see the **login** page (never the
   data — that's RLS doing its job). Sign in with the user you made in step 2.
   Bookmark it / Add to Home Screen.

### Keeping it un-findable
- The `noindex, nofollow` header + meta are already set, so search engines won't
  list it.
- Vercel URLs are unguessable, but the real protection is the login + RLS. If you
  want it fully off the public internet later, add **Vercel Authentication**
  (Project → **Settings → Deployment Protection → Vercel Authentication → Standard
  Protection**) so even the login page requires your Vercel account first.
- **Do not** add a custom domain, marketing copy, or any sign-up/subscription
  element until you say the ethics gate has cleared.

## Redeploys
Every push to `main` (once this PR merges) triggers a Vercel redeploy
automatically. To change the login password: Supabase → Authentication → Users →
your user → reset password.
