import { createClient } from "@/lib/supabase/server";
import { buildBriefView } from "@/lib/brief/view";
import { renderBrief } from "@/lib/brief/render";

// The reader-facing published brief, served as the exact email-safe HTML the
// email sends (buildBriefView + renderBrief is the one shared path, so the web
// view and the email cannot drift). Behind the same auth middleware as the rest
// of the app pre-gate. `week` is a week_start date (YYYY-MM-DD) or "latest".
export const dynamic = "force-dynamic";

export async function GET(_req: Request, { params }: { params: { week: string } }) {
  const supabase = createClient();
  const view = await buildBriefView(supabase, params.week);
  if (!view) {
    return new Response("No published brief for that week.", {
      status: 404,
      headers: { "content-type": "text/plain; charset=utf-8" },
    });
  }
  return new Response(renderBrief(view), {
    headers: {
      "content-type": "text/html; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}
