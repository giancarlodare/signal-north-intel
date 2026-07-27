-- ============================================================================
-- HOTFIX: member RLS recursion (found 2026-07-27 on the preview).
-- brief_items' public-safety clamp subqueries signals; signals' member-read
-- policy subqueries brief_items back. Operators never hit it (role check
-- short-circuits), but MEMBER queries abort with infinite recursion, so the
-- member brief view rendered 0 items. Fix: the cross-table checks move into
-- narrow SECURITY DEFINER functions (fixed search_path, boolean-only), which
-- evaluate without re-entering RLS. Paste in one session; idempotent.
-- ============================================================================
begin;

create or replace function public.sn_lead_signal_public_safety(sid uuid)
returns boolean language sql stable security definer set search_path = public
as $$ select coalesce((select s.public_safety from signals s where s.id = sid), false) $$;

create or replace function public.sn_doc_public_safety(did uuid)
returns boolean language sql stable security definer set search_path = public
as $$ select exists (select 1 from signals s where s.document_id = did and s.public_safety) $$;

create or replace function public.sn_signal_member_visible(sid uuid)
returns boolean language sql stable security definer set search_path = public
as $$ select exists (select 1 from brief_items bi join briefs b on b.id = bi.brief_id
                     where bi.lead_signal_id = sid and bi.included and b.status = 'published') $$;

create or replace function public.sn_doc_member_visible(did uuid)
returns boolean language sql stable security definer set search_path = public
as $$ select exists (select 1 from signals s
                     join brief_items bi on bi.lead_signal_id = s.id
                     join briefs b on b.id = bi.brief_id
                     where s.document_id = did and bi.included and b.status = 'published') $$;

grant execute on function public.sn_lead_signal_public_safety(uuid),
  public.sn_doc_public_safety(uuid), public.sn_signal_member_visible(uuid),
  public.sn_doc_member_visible(uuid) to authenticated, anon;

-- Recreate every policy that crossed tables, now via the definer functions.
drop policy if exists sn_member_read on signals;
create policy sn_member_read on signals for select to authenticated
  using (public.sn_role() = 'operator' or public.sn_signal_member_visible(id));
drop policy if exists sn_gate_clamp on signals;
create policy sn_gate_clamp on signals as restrictive for select to authenticated
  using (public.sn_role() = 'operator' or public.sn_signal_member_visible(id));
drop policy if exists sn_public_safety_clamp on signals;
create policy sn_public_safety_clamp on signals as restrictive for select to authenticated
  using (public.sn_role() = 'operator' or public_safety);

drop policy if exists sn_member_read on brief_items;
create policy sn_member_read on brief_items for select to authenticated
  using (public.sn_role() = 'operator'
         or (included and exists (select 1 from briefs b
              where b.id = brief_items.brief_id and b.status = 'published')));
drop policy if exists sn_gate_clamp on brief_items;
create policy sn_gate_clamp on brief_items as restrictive for select to authenticated
  using (public.sn_role() = 'operator'
         or (included and exists (select 1 from briefs b
              where b.id = brief_items.brief_id and b.status = 'published')));
drop policy if exists sn_public_safety_clamp on brief_items;
create policy sn_public_safety_clamp on brief_items as restrictive for select to authenticated
  using (public.sn_role() = 'operator'
         or public.sn_lead_signal_public_safety(lead_signal_id));

drop policy if exists sn_member_read on documents;
create policy sn_member_read on documents for select to authenticated
  using (public.sn_role() = 'operator' or public.sn_doc_member_visible(id));
drop policy if exists sn_gate_clamp on documents;
create policy sn_gate_clamp on documents as restrictive for select to authenticated
  using (public.sn_role() = 'operator' or public.sn_doc_member_visible(id));
drop policy if exists sn_public_safety_clamp on documents;
create policy sn_public_safety_clamp on documents as restrictive for select to authenticated
  using (public.sn_role() = 'operator' or public.sn_doc_public_safety(id));

commit;
