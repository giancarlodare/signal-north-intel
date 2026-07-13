import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import { signOut } from "../review/actions";
import { CATEGORIES, STATUSES, TIERS, WAVES, label } from "./constants";

export const dynamic = "force-dynamic";

type Prospect = {
  id: string;
  company_name: string;
  category: string;
  tier: string;
  is_reference_candidate: boolean;
  conflict_flag: boolean;
  wave: number;
  status: string;
  hq_location: string | null;
};

function statusClass(status: string): string {
  if (status === "committed" || status === "subscribed") return "tag ok";
  if (status === "declined" || status === "do_not_approach") return "tag no";
  return "tag";
}

export default async function ProspectsPage({
  searchParams,
}: {
  searchParams: { category?: string; tier?: string; status?: string; wave?: string };
}) {
  const supabase = createClient();

  let query = supabase
    .from("prospects")
    .select(
      "id, company_name, category, tier, is_reference_candidate, conflict_flag, wave, status, hq_location"
    )
    .order("wave", { ascending: true })
    .order("is_reference_candidate", { ascending: false })
    .order("company_name", { ascending: true });

  if (searchParams.category) query = query.eq("category", searchParams.category);
  if (searchParams.tier) query = query.eq("tier", searchParams.tier);
  if (searchParams.status) query = query.eq("status", searchParams.status);
  const wave = Number(searchParams.wave);
  if (wave === 1 || wave === 2 || wave === 3) query = query.eq("wave", wave);

  const { data, error } = await query;
  const prospects = (data ?? []) as Prospect[];

  return (
    <main className="page">
      <div className="topbar">
        <h1>Prospects</h1>
        <span className="count">{prospects.length}</span>
        <Link className="link" href="/review">
          Signals
        </Link>
        <Link className="link" href="/procurements">
          Procurements
        </Link>
        <Link className="link" href="/discovery">
          Discovery
        </Link>
        <Link className="link" href="/predictions">
          Predictions
        </Link>
        <form action={signOut}>
          <button className="link" type="submit">
            Sign out
          </button>
        </form>
      </div>

      {/* GET form: filters live in the URL, so they survive reloads and the
          back button. No client JS needed. */}
      <form className="filters" method="get">
        <select name="category" defaultValue={searchParams.category ?? ""}>
          <option value="">All categories</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {label(c)}
            </option>
          ))}
        </select>
        <select name="tier" defaultValue={searchParams.tier ?? ""}>
          <option value="">All tiers</option>
          {TIERS.map((t) => (
            <option key={t} value={t}>
              {label(t)}
            </option>
          ))}
        </select>
        <select name="status" defaultValue={searchParams.status ?? ""}>
          <option value="">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {label(s)}
            </option>
          ))}
        </select>
        <select name="wave" defaultValue={searchParams.wave ?? ""}>
          <option value="">All waves</option>
          {WAVES.map((w) => (
            <option key={w} value={w}>
              wave {w}
            </option>
          ))}
        </select>
        <button type="submit">Filter</button>
      </form>

      {error ? (
        <p className="err">Could not load prospects: {error.message}</p>
      ) : null}

      {!error && prospects.length === 0 ? (
        <p className="empty">No prospects match these filters.</p>
      ) : null}

      {prospects.map((p) => (
        <Link key={p.id} className="cardlink" href={`/prospects/${p.id}`}>
          <article className="card">
            <div className="meta">
              <span className="tag">wave {p.wave}</span>
              <span className="tag">{label(p.tier)}</span>
              <span className={statusClass(p.status)}>{label(p.status)}</span>
              {p.conflict_flag ? <span className="tag warn">conflict</span> : null}
            </div>
            <div className="title">
              {p.is_reference_candidate ? <span className="star">★ </span> : null}
              {p.company_name}
            </div>
            <p className="sub">
              {label(p.category)}
              {p.hq_location ? ` · ${p.hq_location}` : ""}
            </p>
          </article>
        </Link>
      ))}
    </main>
  );
}
