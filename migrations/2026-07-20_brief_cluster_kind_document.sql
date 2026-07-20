-- Grant nuance to the standalone-action-item rule (operator, 2026-07-20):
-- grant_program signals from the SAME source document are ONE brief item --
-- same document means same program, same deadline, same application; the
-- extractor emits one signal per eligibility stream, and per-stream items
-- showed one program twice in the brief. The generator now clusters them by
-- source document (cluster_kind='document', cluster_ref=document_id), so the
-- kind check gains 'document'. Tenders stay standalone per signal: each
-- tender is a separate bid.
alter table brief_items drop constraint if exists brief_items_cluster_kind_check;
alter table brief_items add constraint brief_items_cluster_kind_check
  check (cluster_kind in ('procurement', 'organization', 'signal', 'document'));
