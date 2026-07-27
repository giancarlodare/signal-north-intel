// Wave 3 member dashboard: STAGE-2 FUNCTIONAL SKELETON.
//
// UNSTYLED BY CONTRACT. This proves the member-filtered data layer end to end:
// it lists the published briefs, renders the selected brief's gate-cleared
// items with provenance links, and drives tag filtering via query params
// (server-rendered, no client JS). There is NO styling, NO layout, NO copy
// beyond functional labels and data-testid markers.
//
// AWAITING GIANCARLO'S CLAUDE DESIGN FILES: the presentation (chips, cards,
// layout, masthead) drops in here on top of this data. Logic lives in
// web/lib/portal/data.ts and stays untouched when design lands. Do not add
// CSS or visual structure in this file; replace the markup wholesale when the
// design files arrive.
import { createClient } from "@/lib/supabase/server";
import {
  listPublishedBriefs,
  getBriefItems,
  availableTags,
  filterItems,
  type TagFilter,
} from "@/lib/portal/data";

export const dynamic = "force-dynamic";
export const metadata = {
  robots: { index: false, follow: false, nocache: true },
};

type Search = {
  brief?: string;
  buyer?: string;
  timing?: string;
  defence?: string;
};

export default async function PortalDashboard({
  searchParams,
}: {
  searchParams: Search;
}) {
  const supabase = createClient();
  const briefs = await listPublishedBriefs(supabase);

  if (briefs.length === 0) {
    return (
      <main>
        <p data-testid="portal-empty">No published briefs yet.</p>
      </main>
    );
  }

  const selected =
    briefs.find((b) => b.id === searchParams.brief) ?? briefs[0];
  const allItems = await getBriefItems(supabase, selected.id);
  const tags = availableTags(allItems);
  const filter: TagFilter = {
    buyer: searchParams.buyer ?? null,
    timing:
      searchParams.timing === "imminent" || searchParams.timing === "recent"
        ? searchParams.timing
        : null,
    defenceOnly: searchParams.defence === "1",
  };
  const items = filterItems(allItems, filter);

  // A query-param link that keeps the selected brief and toggles one filter.
  const qp = (patch: Partial<Search>) => {
    const p = new URLSearchParams();
    p.set("brief", selected.id);
    if (filter.buyer) p.set("buyer", filter.buyer);
    if (filter.timing) p.set("timing", filter.timing);
    if (filter.defenceOnly) p.set("defence", "1");
    for (const [k, v] of Object.entries(patch)) {
      if (v === null || v === undefined) p.delete(k);
      else p.set(k, String(v));
    }
    return `/portal?${p.toString()}`;
  };

  return (
    <main data-testid="portal-dashboard">
      {/* Published-brief selector */}
      <nav data-testid="brief-list">
        {briefs.map((b) => (
          <a key={b.id} href={qp({ brief: b.id })} data-active={b.id === selected.id}>
            {b.weekStart}
          </a>
        ))}
      </nav>

      {/* Tag chips (functional; design restyles these) */}
      <div data-testid="tag-chips">
        <a href={qp({ timing: "imminent" })} data-testid="chip-imminent">imminent</a>
        <a href={qp({ timing: "recent" })} data-testid="chip-recent">recent</a>
        {tags.hasDefence ? (
          <a href={qp({ defence: filter.defenceOnly ? undefined : "1" })} data-testid="chip-defence">
            defence-relevant
          </a>
        ) : null}
        {tags.buyers.map((b) => (
          <a key={b} href={qp({ buyer: b })}>{b}</a>
        ))}
        <a href={qp({ buyer: undefined, timing: undefined, defence: undefined })} data-testid="chip-clear">
          clear
        </a>
      </div>

      {/* Items (gate-cleared; each with its provenance link) */}
      <ul data-testid="portal-items">
        {items.map((it) => (
          <li key={it.itemId} data-testid="portal-item">
            <span data-field="headline">{it.headline}</span>
            <span data-field="buyer">{it.buyer ?? ""}</span>
            <span data-field="timing">{it.timingPath}</span>
            <span data-field="event-date">{it.eventDate ?? ""}</span>
            <span data-field="so-what">{it.vendorSoWhat ?? ""}</span>
            {it.sourceUrl ? (
              <a data-field="source" href={it.sourceUrl} target="_blank" rel="noreferrer">
                publisher record
              </a>
            ) : null}
          </li>
        ))}
      </ul>
      <p data-testid="portal-count">{items.length} items</p>
    </main>
  );
}
