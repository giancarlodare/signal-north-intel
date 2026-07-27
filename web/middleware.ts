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
  } = await supabase.auth.getUser();

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
