# Calibration audit design (Phase 5)

Status: DESIGN, committed 2026-07-20. Code follows in a separate PR after this
design is merged.

The standing honesty check that replaced the human approval gate. The corpus
trusts the scorer, so the scorer gets audited: monthly, a stratified sample of
scored signals is re-scored blind through the same extraction path, and the
operator reads a report of agreement and every disagreement. The audit
measures drift and surfaces it; it never corrects it.

## The hard rule: report-only

**No audit result may modify a signal, a score, or a threshold.** Changing a
score, a bar, or a prompt is a human decision made after reading the report.

Enforcement is structural, not aspirational:

- `src/calibration_audit.py` imports ONLY read helpers from supabase_client
  (`fetch_rows_where` / `fetch_all_rows_where`). It has no code path that
  writes to the database.
- A unit test greps the module source and fails if any write verb
  (`insert_`, `update_`, `delete_`, `PATCH`, `POST` to a table) appears.
  Regression to auto-correction cannot land silently.
- The workflow grants the job `contents: read` plus `issues: write` and
  nothing else. The only artifacts a run produces are a GitHub issue (the
  report) and a workflow artifact (the raw JSON).
- Adjudication happens as issue comments and, where the operator decides a
  score should change, as a manual edit through the existing review surfaces.

## What is audited

The extraction scorer is the LLM step in `src/signal_extractor.py`
(claude-opus-4-8, prompts/extraction/v1.txt). Its judgment fields, per signal:

| Field | Type | Why it matters |
|---|---|---|
| `materiality` | 1..5 | Gates the brief bar and the relevance lens |
| `signal_type` | enum | Derives `evidence_grade` via taxonomy (deterministic) |
| `confidence` | enum | Reader-facing certainty |

`evidence_grade` itself is NOT LLM-scored (it is `taxonomy.grade(signal_type,
doc_type)`), so grade drift is reported as a derived consequence of
signal_type drift, never audited independently.

## Sampling: ~30 per month, stratified by evidence_grade

- Population: non-suppressed signals with an `extracted_by` stamp (LLM-scored)
  whose source document still holds content, created in the trailing 90 days
  (recent scores are the ones drift affects; older scores were audited in
  earlier months).
- Strata: evidence_grade 1..5, target 6 per grade (30 total). High grades are
  always represented rather than swamped by the grade-1/2 bulk.
- A grade with fewer than 6 eligible signals contributes ALL of them and the
  shortfall is stated in the report. **Never padded** from other grades: a
  thin stratum is a fact, not a gap to hide.
- Random within stratum, seeded with the run date so a re-run of the same
  month's audit draws the same sample (reproducible adjudication).
- `extracted_by` (prompt version) is recorded per sampled signal and NOT
  filtered on. On the scheduled run this measures drift under a stable prompt;
  on a manual run after a prompt or collector change it measures exactly that
  change's effect, which is the point of the dispatch trigger.

## Blind re-score protocol

For each sampled signal:

1. Fetch its source document (content, doc_type, title, url).
2. Run the SAME extraction path used in production: same module, same prompt
   file, same model (claude-opus-4-8), same response schema. The call sees
   only the document, never the original signal or its scores.
3. Match the audited signal to one of the re-extracted signals. The extractor
   emits one signal per finding, so matching is by normalized token overlap on
   `quote_or_line` first, then `title` (threshold ~0.5 Jaccard; the matcher is
   a pure function with unit tests). Best match wins; one re-extracted signal
   matches at most one audited signal.
4. If nothing matches, the signal is recorded as **not reproduced**: a
   first-class disagreement category (the scorer no longer even finds the
   signal), not a silent drop.

## What counts as agreement

**Headline number: exact match, per field.** Within-one materiality is
reported as a secondary number, never the headline. Reasoning:

- The grade boundaries ARE the product. materiality>=3 admits a recent event
  to the brief, materiality>=4 passes the relevance lens, and signal_type
  fixes the evidence grade the reader sees. A scorer that is "close" on the
  number but on the other side of a boundary produces a different brief; an
  agreement definition that forgives ±1 would grade that failure as success
  and hide exactly the drift the audit exists to catch.
- Within-one is still diagnostic, so it is kept as the secondary rate: a high
  within-one rate with a sagging exact rate means calibration wobble at the
  boundaries (re-anchor the rubric wording in the prompt); a low within-one
  rate means category error (the scorer is reading the documents differently,
  a bigger problem). The two numbers together say WHICH failure is happening;
  either alone cannot.
- `signal_type` and `confidence` are enums with no distance metric: exact
  match only. Derived evidence_grade equality is reported alongside
  signal_type so a type flip that happens to preserve the grade is visible
  as such.

**Boundary-crossing count.** Because the boundaries are the product, the
report also counts, within the materiality disagreements, how many CROSS a
decision boundary in force (the 3 brief bar, the 4 lens bar): a 4 to 3 flip
changes the draft; a 5 to 4 flip changes nothing a reader sees. Same
disagreement distance, different product impact; the report says which is
which so adjudication can start with the flips that alter the brief.

## Comparison and report

Per matched pair, three comparisons: `materiality` (exact headline, within
±1 secondary, boundary-crossing flagged), `signal_type` (exact; derived
evidence_grade equality reported alongside), `confidence` (exact).

The report contains, in order:

1. **Header**: sample size per grade (with shortfalls), prompt versions seen,
   model, run trigger (scheduled or manual + reason).
2. **Agreement table**: overall and per evidence grade, per field, with the
   ±1 materiality rate beside the exact rate.
3. **Every disagreement**, one block each: signal title, buyer, doc_type,
   document URL, `quote_or_line`, original scores vs blind re-scores, and the
   disagreement category (field mismatch or not-reproduced). Everything the
   operator needs to adjudicate without opening the database.
4. **Honest caveats**: sample shortfalls, documents that could not be
   re-fetched (excluded and counted, never substituted), API failures.

## Delivery: a GitHub issue per run (proposed)

Each run opens one issue titled `Calibration audit YYYY-MM`, labeled
`calibration-audit`, body = the report above; the raw per-signal JSON is
attached as a workflow artifact (90-day retention) for any later backtest.

Why an issue rather than a committed markdown report:

- It lands in the notification channel the operator already watches (same
  place Actions failures arrive), so it will actually be seen.
- Adjudication needs a discussion surface; issue comments are exactly that,
  and closing the issue records that the month was adjudicated.
- Report-only extends to the repo: the audit job needs no push access to
  main and writes no commits. A bot committing reports to main would grant
  the audit a write surface it should not have.

Trade-off accepted: issues are less greppable than files in-repo. The JSON
artifact plus the issue archive covers the history; if a durable in-repo
ledger is wanted later, the operator can curate one from adjudicated issues.

## Triggers

- **Scheduled**: monthly, first Monday ~7am ET (the dual-cron EDT/EST guard
  pattern used by the daily workflows).
- **Manual**: `workflow_dispatch` with a free-text `reason` input (e.g.
  "post prompt-v2 change"), recorded in the report header. Run it after any
  collector or extraction-prompt change.

## Cost

Per re-score: one extraction call on Opus 4.8 ($5/M input, $25/M output).
Typical document + prompt ≈ 5K input tokens, structured output ≈ 600 tokens:
about $0.04 per document. **~30 re-scores ≈ $1.30/month**; a pathological
month of long documents stays under ~$3. Rounding error, as expected.

## Failure modes (loud, never silent)

- Anthropic API failure mid-run: the job fails RED. No partial report is
  posted as if complete; the next run (or a manual re-dispatch) redoes the
  month.
- Fewer than ~10 eligible signals in the window: the report is still posted,
  says so plainly, and the agreement numbers carry a small-sample warning.
  A thin audit is stated, never padded.
- Issue creation failure after a successful audit: the job fails RED and the
  report is still recoverable from the workflow artifact and the job log.

## Non-goals

- No auto-correction of scores, thresholds, prompts, or suppression.
- Not a replacement for spot human review in the /review surface; it is the
  scheduled floor under it.
- No cross-model comparison (that was the one-time Haiku-vs-Opus field test);
  the audit compares the production scorer against itself over time.

## Implementation sketch (next PR)

- `src/calibration_audit.py`:
  - `stratified_sample(signals, per_grade=6, seed=...)` (pure)
  - `match_reextracted(original, candidates)` (pure, Jaccard matcher)
  - `compare(original, matched)` (pure, returns per-field agreement record)
  - `render_report(results, meta)` (pure, returns markdown)
  - `run(dry_run=...)`: fetch, sample, re-score via
    `signal_extractor.extract_signals`, compare, emit JSON + markdown to
    stdout/files. No DB writes, no issue creation (that is the workflow's
    step, via GITHUB_TOKEN).
- `.github/workflows/calibration-audit.yml`: monthly cron + dispatch;
  `permissions: contents: read, issues: write`; runs the module, posts the
  issue from the emitted markdown, uploads the JSON artifact.
- `tests/test_calibration_audit.py`: stratification (representation,
  shortfall, no padding, seed reproducibility), matcher (match, no-match,
  one-to-one), comparison metrics, report rendering (disagreements listed
  with both scores), and the no-write-verbs source grep.
