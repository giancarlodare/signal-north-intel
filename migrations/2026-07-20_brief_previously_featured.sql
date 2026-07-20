-- brief_items.previously_featured: the generator marks draft items whose story
-- already appeared in a PRIOR PUBLISHED brief (same lead signal, or the same
-- cluster carried across weeks), so the editor shows new vs carried at a
-- glance. Display-only: it never changes selection, ranking, or the render.
alter table brief_items
  add column if not exists previously_featured boolean not null default false;
