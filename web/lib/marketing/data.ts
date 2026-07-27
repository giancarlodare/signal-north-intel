// Marketing-site live data (operator rule 2026-07-27): every element that
// would be wrong in a month if untouched renders from these queries or is
// OMITTED. There is no static fallback for time-sensitive content.
//
// Source: the anon-executable SECURITY DEFINER functions in
// migrations/2026-07-27_marketing_public_data.sql (fixed shapes, aggregate
// and list data only). Until the operator pastes that migration the RPCs do
// not exist; every getter then returns null and the callers omit their
// sections, so the site can never show stale or fabricated figures.
//
// Cached for 30 minutes per query: fresh enough for deadlines counted in
// days, cheap enough for a public page.
import { createClient } from "@supabase/supabase-js";
import { unstable_cache } from "next/cache";

const REVALIDATE_S = 1800;

function anonClient() {
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    { auth: { persistSession: false, autoRefreshToken: false } },
  );
}

async function rpc<T>(fn: string): Promise<T | null> {
  try {
    const { data, error } = await anonClient().rpc(fn);
    if (error) return null;
    return (data as T) ?? null;
  } catch {
    return null;
  }
}

export interface MarketingStats {
  police_and_boards: number;
  councils_ministries_departments: number;
  live_contracts_with_end_dates: number;
  live_contract_value_cad: number;
  earliest_award_year: number | null;
  years_of_award_history: number;
  documents_last_7_days: number;
}

export interface MarketingCoverage {
  services: string[];
  oversight: string[];
  government: string[];
}

export interface ClosingSoonRow {
  title: string;
  buyer: string | null;
  kind: "Tender" | "Grant";
  close_on: string;
  days_left: number;
}

export interface ClosingSoon {
  total_open: number;
  rows: ClosingSoonRow[];
}

export interface RecentAward {
  title: string;
  vendor: string | null;
  end_year: number | null;
}

export const getMarketingStats = unstable_cache(
  async () => rpc<MarketingStats>("marketing_stats"),
  ["marketing-stats"],
  { revalidate: REVALIDATE_S },
);

export const getMarketingCoverage = unstable_cache(
  async () => rpc<MarketingCoverage>("marketing_coverage"),
  ["marketing-coverage"],
  { revalidate: REVALIDATE_S },
);

export const getClosingSoon = unstable_cache(
  async () => {
    const data = await rpc<ClosingSoon>("marketing_closing_soon");
    // A panel with zero rows is omitted, same as no data: the design's
    // "Closing soon" head over an empty list reads as breakage.
    if (!data || !Array.isArray(data.rows) || data.rows.length === 0) return null;
    return data;
  },
  ["marketing-closing-soon"],
  { revalidate: REVALIDATE_S },
);

export const getRecentAwards = unstable_cache(
  async () => {
    const data = await rpc<RecentAward[]>("marketing_recent_awards");
    if (!data || data.length === 0) return null;
    return data;
  },
  ["marketing-recent-awards"],
  { revalidate: REVALIDATE_S },
);

// Pure formatting lives in ./format (unit-tested without Next); re-exported
// here so page code has one import site.
export { formatCadCompact, formatCountFloor } from "./format";
