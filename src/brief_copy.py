"""Deterministic draft copy for the weekly brief: a per-item vendor read and the
top-of-brief "The Read" paragraph. The operator sharpens these in the editor;
the draft is the scaffold, the edits are the value.

Everything here is assembled from what we already hold (doc_type, buyer, amount,
timing, title text) and never fabricates: a clause appears only when its input
is present, and the one inference we make (the plausible field of competitors)
is derived from keywords IN the title and stated as a reading, not a claim of
fact. No LLM, so it is deterministic and unit-testable. No em dashes.
"""
from collections import Counter
from datetime import date


def _fmt_amount(n) -> str | None:
    """Compact CAD, or None for a missing/non-positive amount (never invent one)."""
    try:
        v = float(n)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    if v >= 1_000_000:
        return f"${v / 1_000_000:.1f}M"
    if v >= 1_000:
        return f"${round(v / 1_000)}K"
    return f"${round(v)}"


# Keyword -> plausible field of competitors/applicants. Derived from the title's
# own words, so it is a reading of the posted work, not a fabricated claim.
_FIELD_HINTS = [
    (("renovation", "construction", "roof", "hvac", "building", "facility",
      "interior", "exterior", "repair", "masonry", "structural"),
     "general contractors with public-sector experience"),
    (("scada", "integration", "software", "network", "cabling", "licens",
      "platform", "application", "cyber", "data centre", "server", "hardware"),
     "systems integrators and IT suppliers"),
    (("consulting", "design", "engineering", "study", "assessment", "master plan",
      "inspection", "survey"),
     "engineering and consulting firms"),
    (("supply", "purchase", "equipment", "vehicle", "tractor", "goods", "meters"),
     "equipment suppliers"),
    (("maintenance", "cleaning", "grounds", "landscap", "snow", "tree", "waste"),
     "facilities and maintenance contractors"),
]


def plausible_field(title: str) -> str | None:
    t = (title or "").lower()
    for keys, label in _FIELD_HINTS:
        if any(k in t for k in keys):
            return label
    return None


def draft_item_note(*, doc_type: str | None, timing_path: str | None,
                    buyer: str | None, title: str | None, amount_cad=None,
                    streams: list | None = None) -> str:
    """A 2 to 3 sentence vendor read for one item. Structurally true, keyed on
    the document type and timing, with the amount and plausible field added only
    when we have them."""
    # The headline (title) renders directly above the note, so the note never
    # restates it: echoing the title both duplicates the headline and doubles the
    # subject when the title already embeds the buyer ("Region of Peel tenders X"
    # -> "Region of Peel has opened Region of Peel tenders X"). The note refers to
    # the opportunity as "this" and leads with the buyer instead.
    who = (buyer or "The buyer").strip()
    is_prequal = "prequalif" in (title or "").lower()
    s: list[str] = []

    if doc_type == "tender_notice":
        if timing_path == "imminent":
            if is_prequal:
                s.append(f"{who} is prequalifying vendors for this, assembling a shortlist.")
                s.append("A vendor not already known to them needs a qualified partner to make "
                         "the list before the deadline.")
            else:
                s.append(f"{who} has this out for bids, closing inside the window.")
                s.append("A vendor without a track record with this buyer should be lining up "
                         "references and a local partner before it closes.")
        else:
            # Peel tender dates are the CLOSE date, so a recent tender has just
            # closed: the award is the next event, not a bid opportunity.
            s.append(f"{who} has just closed bids on this.")
            s.append("The award is the next event, so watch for the winner and note the buyer "
                     "and category to be positioned for the recompete.")
    elif doc_type == "award_notice":
        s.append(f"{who} has awarded this contract.")
        s.append("The award is settled, so for a challenger the value is the recompete: note "
                 "the buyer and the category and be positioned before the next cycle opens.")
    elif doc_type in ("grant_program", "grant_award"):
        if streams and len(streams) > 1:
            # One program, several eligibility streams (clustered from one
            # source document): one deadline, one application, so the streams
            # are enumerated here rather than shown as separate items.
            shown = [t.strip() for t in streams[:5] if t and t.strip()]
            extra = len(streams) - len(shown)
            listed = "; ".join(shown) + (f"; and {extra} more" if extra > 0 else "")
            s.append(f"{who} is accepting applications under one program spanning "
                     f"{len(streams)} eligibility streams: {listed}.")
            s.append("One deadline and one application process cover every stream, so "
                     "confirm which stream fits before committing proposal effort.")
        else:
            s.append(f"{who} is accepting applications.")
            s.append("Eligibility is fixed by the program rules, so confirm fit before committing "
                     "proposal effort; the deadline is firm and does not move.")
    elif doc_type == "board_minutes":
        s.append(f"{who} has taken a board decision here.")
        s.append("A board approval is the commitment that precedes a tender, so engage the "
                 "buyer now, before an RFP posts and the field is set.")
    else:
        s.append(f"{who} is the party to watch on this one.")

    # Field and amount, when present, close the read as ONE sentence, so the note
    # stays within 2 to 3 sentences however much we hold. The plausible field is
    # still read from the title's own words (the title is our input, just not
    # echoed into the prose).
    field = plausible_field(title or "")
    amt = _fmt_amount(amount_cad)
    if field and amt:
        s.append(f"The work reads as {field}, reported value {amt}.")
    elif field:
        s.append(f"The work reads as {field}.")
    elif amt:
        s.append(f"Reported value {amt}.")
    return " ".join(s)


def _window_phrase(c: dict) -> str:
    """', closes Sep 1, 2026' style clause from the cluster's own event date,
    or empty when there is no date (never fabricate one)."""
    raw = c.get("soonest_date")
    if not raw:
        return ""
    try:
        d = date.fromisoformat(str(raw)[:10])
    except ValueError:
        return ""
    if c.get("timing_path") != "imminent":
        # A recent item's date may be month-precision (stored day=01); naming
        # the day here could fabricate one. The item row below renders it with
        # the correct precision label, so The Read names no date for these.
        return ""
    when = f"{d.strftime('%b')} {d.day}, {d.year}"
    verb = ("applications close" if c.get("doc_type") == "grant_program"
            else "closes")
    return f", {verb} {when}"


def _lead_phrase(c: dict) -> str:
    title = (c.get("lead_title") or "the item below").strip()
    if len(title) > 90:
        title = title[:87] + "..."
    org = c.get("org")
    who = f" ({org})" if org and org.lower() not in title.lower() else ""
    return f"{title}{who}{_window_phrase(c)}"


def draft_the_read(clusters: list) -> str:
    """One paragraph on the reader's market this week: the lead opportunity
    first, then the shape of the week. EDITORIAL POV RULE (operator
    2026-07-26, the client-facing gate applied to editorial): the brief shows
    the client their world and our conclusions, never our machinery. No
    bars, thresholds, item counts as process, or corpus totals here;
    selection accounting lives in the methodology footnote."""
    n = len(clusters)
    if n == 0:
        return ("No new timing-relevant movement in your market this week. "
                "The standing exhibits below carry the through-line; a quiet "
                "week is reported as one, never padded.")
    imminent = [c for c in clusters if c.get("timing_path") == "imminent"]
    lead = imminent[0] if imminent else clusters[0]
    parts: list[str] = []
    if len(imminent) == 1:
        parts.append(f"One imminent opportunity: {_lead_phrase(lead)}.")
    elif len(imminent) > 1:
        parts.append(f"{len(imminent)} windows are open or closing this week, "
                     f"led by {_lead_phrase(lead)}.")
    else:
        parts.append(f"The week's movement has settled. Most recent: "
                     f"{_lead_phrase(lead)}.")
    buyers = Counter(c.get("org") for c in clusters if c.get("org"))
    if buyers:
        top, cnt = buyers.most_common(1)[0]
        if cnt >= 2 and cnt < n:
            parts.append(f"{top} is the most active buyer this week, behind "
                         f"{cnt} of the {n} developments.")
        elif cnt >= 2:
            parts.append(f"All of this week's movement is {top}'s.")
    if imminent and len(imminent) >= n - len(imminent):
        parts.append("The read is to act inside the windows below, not to "
                     "review what has already closed.")
    elif not imminent:
        parts.append("The value is in what the settled awards signal about "
                     "the next cycle.")
    return " ".join(parts)
