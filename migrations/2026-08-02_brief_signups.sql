-- ============================================================================
-- Free-brief signups: the email-capture list behind "Get the free brief"
-- (operator 2026-08-02).
--
-- THE POINT OF THIS TABLE IS THAT IT IS NOT AN ACCOUNT. The operator's ruling
-- keeps the two public actions on the marketing site distinct because they are
-- distinct products:
--
--   "Get the free brief"  email capture only. No account, no login, no row in
--                         auth.users, no entitlement of any kind. It feeds the
--                         PARTIAL send list and nothing else. This table.
--   "Join Weekly"         a real signup: Supabase account, confirm link,
--                         /portal/account, checkout. Nothing to do with here.
--
-- Free having no login is deliberate: it keeps the entitlement layer small
-- until Pro arrives. Collapsing the two into one form would put every free
-- reader into the auth system to buy nothing, which is the cost this avoids.
--
-- ACCESS SHAPE, same asymmetry as tier_inquiries and for the same reason:
--   INSERT  yes, for anon -- the marketing site is public and unauthenticated
--   SELECT  no, for anyone but the operator -- one reader can never enumerate
--           the list, which is a list of named people at named organisations
--
-- CASL. Entering an address and pressing "Get the free brief" is a request for
-- the thing, which is express consent, and `consent_source` records where the
-- request was made so the consent is evidenced rather than asserted. Two
-- columns are here AHEAD of the send half (#57) so honouring them later is a
-- settings change and not a second migration:
--   confirmed_at      double opt-in, if the send half chooses to require it.
--                     NULL today because no confirmation mail exists to send
--                     yet. The send half decides; see the note below.
--   unsubscribed_at   set by the unsubscribe link that every CASL message
--                     must carry (already flagged in web/lib/brief/render.ts).
--
-- OPEN DECISION FOR THE SEND HALF, stated here rather than assumed: whether
-- the first real send goes to unconfirmed rows (express consent, CASL-
-- sufficient) or only to rows with confirmed_at set (double opt-in, which
-- also stops someone subscribing a colleague's address). Nothing in this
-- migration forces either answer. It must be answered before the first send,
-- not discovered after it.
-- ============================================================================
begin;

create table if not exists brief_signups (
  id               uuid primary key default gen_random_uuid(),
  -- Stored already-lowercased by the server action, so this constraint is a
  -- real one-address-one-row rule rather than a case-sensitive near-miss.
  email            text not null unique,
  -- Where the request was made ("home-hero", "pricing-free"). The evidence
  -- half of express consent, and it tells the operator which surface works.
  consent_source   text,
  confirmed_at     timestamptz,
  unsubscribed_at  timestamptz,
  -- Capability token for the unsubscribe link: it must work from an email
  -- client with no session, so the link carries proof of nothing but itself.
  unsubscribe_token uuid not null default gen_random_uuid(),
  created_at       timestamptz not null default now()
);

create index if not exists idx_brief_signups_created
  on brief_signups (created_at desc);

-- The send half reads this: live list = consented, not unsubscribed.
create index if not exists idx_brief_signups_sendable
  on brief_signups (created_at desc)
  where unsubscribed_at is null;

alter table brief_signups enable row level security;

-- Anyone (including anon) may add themselves. `with check` constrains what
-- they may write: a submitter cannot mark their own address confirmed, and
-- cannot pre-set an unsubscribe state. Those two columns belong to us.
drop policy if exists sn_brief_signup_insert on brief_signups;
create policy sn_brief_signup_insert on brief_signups
  for insert to anon, authenticated
  with check (confirmed_at is null and unsubscribed_at is null);

-- Reads are OPERATOR ONLY. This is a list of named people at named
-- organisations; no member and certainly no anon ever reads it back.
drop policy if exists sn_brief_signup_read on brief_signups;
create policy sn_brief_signup_read on brief_signups
  for select to authenticated
  using (public.sn_role() = 'operator');

-- Updates (confirmed_at, unsubscribed_at) are operator only for now. When the
-- unsubscribe route ships it runs service-role, which bypasses RLS, so no
-- anon update grant is needed here and none is given. No delete policy: an
-- unsubscribe is recorded, not erased, because erasing it loses the proof
-- that we were asked to stop.
drop policy if exists sn_brief_signup_update on brief_signups;
create policy sn_brief_signup_update on brief_signups
  for update to authenticated
  using (public.sn_role() = 'operator')
  with check (public.sn_role() = 'operator');

grant insert on table brief_signups to anon, authenticated;
grant select, update on table brief_signups to authenticated;

commit;
