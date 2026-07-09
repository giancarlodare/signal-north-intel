# Prompt Library Changelog

All notable changes to Signal North prompts. Each released version is
immutable; changes ship as a new version with an entry here. The version is
stamped onto produced artifacts as `<name>@v<version>` (e.g. `extraction@v1`).

## extraction

### v1 — 2026-07-09
- Initial versioned extraction prompt, ported from the PR #6 inline prompt
  (`signal_extractor.EXTRACTION_PROMPT`) and moved into the prompt library.
- Behavioural changes vs. the ported original:
  - Always returns `organization_name` (raw, as written in the document) even
    when unsure, so unresolved orgs can be resolved later instead of dropped.
  - Explicitly told the input may be title-only, and to mark confidence
    accordingly (a headline alone rarely supports `confirmed`).
- **Pending before first production run:** the `signal_type` and
  `category_slug` value lists embedded in the prompt must be verified against
  the live DB enums / `categories.slug` values. Ported as-is from PR #6; that
  code inserted successfully, so they are likely valid, but confirm before
  extracting at scale.
