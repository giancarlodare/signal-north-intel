import { createServerClient, type CookieOptions } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import { gate, portalEnabled, roleFromUser } from "@/lib/auth/roles";

type CookieToSet = { name: string; value: string; options?: CookieOptions };

// Refreshes the Supabase auth session on every request and gates access:
// unauthenticated users can only reach /login. This is the single security
// boundary for a publicly-reachable Vercel URL, so it runs on all routes.
export async function middleware(request: NextRequest) {
  let response = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet: CookieToSet[]) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value)
          );
          response = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options)
          );
        },
      },
    }
  );

  const {
    data: { user },
    error: authError,
  } = await supabase.auth.getUser();
  if (authError && !/session/i.test(authError.message ?? "")) {
    // VISIBILITY, not behavior (operator 2026-08-04, the live-window /pricing
    // bounce). The gate collapses ANY getUser failure into "unauthenticated",
    // which is the right fail-closed policy -- but without this line a Supabase
    // Auth outage or per-IP rate limit (429) is indistinguishable from a
    // signed-out visitor, and a real member bounced to /login looks like
    // nothing in the logs. Missing-session errors are excluded: an anonymous
    // visitor is normal traffic, not a failure.
    console.error(
      "[middleware] auth check failed (treating as unauthenticated):",
      authError.status ?? "", authError.message,
    );
  }

  const path = request.nextUrl.pathname;

  // Wave 3 role gate. While PORTAL_ENABLED is off (the default), gate()
  // returns exactly the pre-Wave-3 outcomes: auth-only, no role gating, and
  // the member surface 404s. So this branch is inert in production until the
  // operator flips the flag AND the DDL has stamped the operator role.
  const outcome = gate({
    enabled: portalEnabled(),
    authenticated: Boolean(user),
    role: roleFromUser(user),
    path,
  });

  if (outcome === "to-login") {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    return NextResponse.redirect(url);
  }
  if (outcome === "to-portal") {
    const url = request.nextUrl.clone();
    url.pathname = "/portal";
    return NextResponse.redirect(url);
  }
  if (outcome === "not-found") {
    // The member surface does not exist while dark; a 404 hides it.
    return new NextResponse(null, { status: 404 });
  }

  // Signed-in users landing on /login go to their home surface.
  if (user && path === "/login") {
    const url = request.nextUrl.clone();
    url.pathname = roleFromUser(user) === "member" ? "/portal" : "/corpus";
    return NextResponse.redirect(url);
  }

  return response;
}

export const config = {
  // Run on everything except static assets.
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
