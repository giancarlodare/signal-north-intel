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
                    buyer: str | None, title: str | None, amount_cad=None) -> str:
    """A 2 to 3 sentence vendor read for one item. Structurally true, keyed on
    the document type and timing, with the amount and plausible field added only
    when we have them."""
    who = (buyer or "The buyer").strip()
    what = (title or "this opportunity").strip()
    s: list[str] = []

    if doc_type == "tender_notice" and timing_path == "imminent":
        s.append(f"{who} has opened {what}.")
        if "prequalif" in what.lower():
            s.append("This is a prequalification, so the buyer is assembling a shortlist; "
                     "a vendor not already known to them needs a qualified partner to make the list.")
        else:
            s.append("Bids close inside the window, so a vendor without a track record with "
                     "this buyer should be lining up references and a local partner now.")
    elif doc_type == "award_notice":
        s.append(f"{who} has awarded {what}.")
        s.append("The award is settled, so for a challenger the value is the recompete: note "
                 "the buyer and the category and be positioned before the next cycle opens.")
    elif doc_type in ("grant_program", "grant_award"):
        s.append(f"{who} is accepting applications for {what}.")
        s.append("Eligibility is fixed by the program rules, so confirm fit before committing "
                 "proposal effort; the deadline is firm and does not move.")
    elif doc_type == "board_minutes":
        s.append(f"{who} has taken a board decision on {what}.")
        s.append("A board approval is the commitment that precedes a tender, so engage the "
                 "buyer now, before an RFP posts and the field is set.")
    else:
        s.append(f"{who}: {what}.")

    # Field and amount, when present, close the read as ONE sentence, so the note
    # stays within 2 to 3 sentences however much we hold.
    field = plausible_field(what)
    amt = _fmt_amount(amount_cad)
    if field and amt:
        s.append(f"The work reads as {field}, reported value {amt}.")
    elif field:
        s.append(f"The work reads as {field}.")
    elif amt:
        s.append(f"Reported value {amt}.")
    return " ".join(s)


def draft_the_read(clusters: list, peel_recent_awards: int | None = None) -> str:
    """One paragraph tying the week's items to a view, from the item mix and one
    corpus scale fact. The operator rewrites this into real editorial voice."""
    n = len(clusters)
    if n == 0:
        return ("A quiet week for new signals. The standing exhibit below carries the "
                "through-line; nothing timing-relevant cleared our materiality bar.")
    imminent = sum(1 for c in clusters if c.get("timing_path") == "imminent")
    buyers = Counter(c.get("org") for c in clusters if c.get("org"))
    parts: list[str] = [
        f"{n} item{'s' if n != 1 else ''} cleared the bar this week, "
        f"{imminent} of them acting or closing soon."
    ]
    if buyers:
        top, cnt = buyers.most_common(1)[0]
        if cnt >= 2:
            parts.append(f"{top} is the dominant buyer, with {cnt} of them.")
    if imminent >= n - imminent:
        parts.append("The week is forward-leaning: the read is to act inside the windows below, "
                     "not to review what has already closed.")
    else:
        parts.append("The week is retrospective: most of what moved has settled, so the value "
                     "is in what the awards signal about the next cycle.")
    if peel_recent_awards and peel_recent_awards > 0:
        parts.append(f"For scale, Region of Peel has closed {peel_recent_awards} contracts over "
                     "the last four quarters, so its municipal cadence is steady.")
    return " ".join(parts)
