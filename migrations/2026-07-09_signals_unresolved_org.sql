-- ============================================================================
-- Signals: allow storing signals whose organization could not be resolved,
-- instead of dropping them. Required by src/signal_extractor.py.
--
-- Reviewed, additive, transactional, idempotent — safe to run more than once:
--   * DROP NOT NULL is a no-op if the column is already nullable.
--   * ADD COLUMN IF NOT EXISTS is a no-op if the column already exists.
--   * Wrapped in a single transaction so a failure leaves nothing half-applied.
-- ============================================================================
begin;

-- signals.organization_id was NOT NULL, which forced the old extractor to
-- discard any signal it couldn't resolve to an org. Make it nullable so those
-- signals can be stored and resolved later.
alter table signals alter column organization_id drop not null;

-- Preserve the raw organization name the model reported, for later resolution.
alter table signals add column if not exists unresolved_org_name text;

-- Explicit review flag so the (upcoming) review page can surface signals that
-- need a human to pick the right organization.
alter table signals add column if not exists needs_org_resolution boolean not null default false;

commit;
