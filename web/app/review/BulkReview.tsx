"use client";

import { useRef, useState, useTransition } from "react";
import { approveMany, rejectMany } from "./actions";

// A signal flattened on the server into exactly what the card needs, so the
// client component carries no PostgREST array/object ambiguity and no secrets.
export type ReviewSignal = {
  id: string;
  title: string;
  summary: string | null;
  signal_type: string;
  confidence: string;
  materiality: number;
  evidence_grade: number | null;
  needs_org_resolution: boolean;
  org_label: string;
  source_url: string | null;
  event_date: string;
  doc_type: string | null;
};

const RUNGS = ["ungraded", "chatter", "intent", "commitment", "in_market", "awarded"];
const gradeLabel = (g: number | null) => RUNGS[g ?? 0] ?? "ungraded";

// Desktop bulk review: one form wraps every card so the checked rows submit
// natively as repeated "ids" fields (server reads FormData.getAll("ids")).
// Selection state here only drives the count, select-all, and the sticky bar;
// correctness comes from the native checkboxes, not from JS state. Approve and
// Reject are the SAME two server actions the single-card flow uses, applied to
// the checked set -- never to a whole filter blindly.
export default function BulkReview({ signals }: { signals: ReviewSignal[] }) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [note, setNote] = useState("");
  const [pending, startTransition] = useTransition();
  const formRef = useRef<HTMLFormElement>(null);

  const allSelected = signals.length > 0 && selected.size === signals.length;
  const toggle = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const toggleAll = () =>
    setSelected(allSelected ? new Set() : new Set(signals.map((s) => s.id)));

  // Run a bulk action on the checked rows, then clear the selection and the
  // note so the completed action is visibly done (the note field used to keep
  // its text, which read as "nothing happened"). The checked checkboxes + note
  // are read from the live form, so what is written is exactly what is shown.
  const run = (action: (fd: FormData) => Promise<void>) => {
    if (!formRef.current || selected.size === 0) return;
    const fd = new FormData(formRef.current);
    startTransition(async () => {
      await action(fd);
      setSelected(new Set());
      setNote("");
    });
  };

  if (signals.length === 0) {
    return <p className="empty">Nothing to review for this filter.</p>;
  }

  return (
    <form ref={formRef} className="bulk">
      <div className="selectall">
        <label className="checkrow">
          <input type="checkbox" checked={allSelected} onChange={toggleAll} />
          Select all {signals.length} shown
        </label>
      </div>

      <div className="cards">
        {signals.map((s) => {
          const checked = selected.has(s.id);
          const mClass = s.materiality >= 5 ? "m5" : s.materiality >= 4 ? "m4" : "";
          const g = s.evidence_grade ?? 0;
          const gClass = g >= 4 ? "g-strong" : g === 3 ? "g-mid" : "g-weak";
          return (
            <label
              key={s.id}
              className={"card selectable" + (checked ? " selected" : "")}
            >
              <div className="meta">
                <input
                  type="checkbox"
                  name="ids"
                  value={s.id}
                  checked={checked}
                  onChange={() => toggle(s.id)}
                />
                <span className="tag event">{s.event_date}</span>
                <span className={"tag grade " + gClass}>{gradeLabel(s.evidence_grade)}</span>
                <span className={"tag " + mClass}>M{s.materiality}</span>
                <span className="tag">{s.confidence}</span>
                <span className="tag">{s.signal_type}</span>
                {s.doc_type ? <span className="tag">{s.doc_type}</span> : null}
                {s.needs_org_resolution ? <span className="tag warn">org?</span> : null}
              </div>
              <div className="title">{s.title}</div>
              {s.summary ? <p className="summary">{s.summary}</p> : null}
              <p className="sub">
                {s.org_label}
                {s.source_url ? (
                  <>
                    {" · "}
                    <a href={s.source_url} target="_blank" rel="noreferrer">
                      source
                    </a>
                  </>
                ) : null}
              </p>
            </label>
          );
        })}
      </div>

      {/* Sticky action bar: acts on the checked rows. Reject note is optional
          and applies to the whole batch. */}
      <div className="bulkbar">
        <span className="count">
          {selected.size > 0
            ? `${selected.size} selected`
            : "Select signals to act on"}
        </span>
        <input
          className="note"
          name="note"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Reject reason (optional, applies to batch)"
        />
        <button
          className="approve"
          type="button"
          onClick={() => run(approveMany)}
          disabled={selected.size === 0 || pending}
        >
          {pending ? "Working…" : "Approve selected"}
        </button>
        <button
          className="reject"
          type="button"
          onClick={() => run(rejectMany)}
          disabled={selected.size === 0 || pending}
        >
          {pending ? "Working…" : "Reject selected"}
        </button>
      </div>
    </form>
  );
}
