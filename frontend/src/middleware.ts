import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

import { env } from "@/lib/env";
import { isPublicRoute, routes } from "@/lib/routes";

/**
 * Refresh the session on every request, and keep signed-out users out of the
 * app shell.
 *
 * This is a convenience gate, not the security boundary: it only decides which
 * page renders. Every piece of tenant data is authorised by the backend against
 * the JWT, so a forged cookie here yields empty screens, not someone else's
 * reports.
 */
export async function middleware(request: NextRequest) {
  // Supabase writes rotated auth cookies onto this response as a side effect of
  // `getUser()` below.
  let response = NextResponse.next({ request });

  const supabase = createServerClient(env.supabaseUrl, env.supabaseKey, {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet) {
        cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
        response = NextResponse.next({ request });
        cookiesToSet.forEach(({ name, value, options }) =>
          response.cookies.set(name, value, options),
        );
      },
    },
  });

  // `getUser` revalidates against Supabase rather than trusting the cookie's
  // contents, which is the point of doing this in middleware at all. It also
  // rotates the token when it is close to expiry.
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const { pathname } = request.nextUrl;

  if (!user && !isPublicRoute(pathname)) {
    const url = request.nextUrl.clone();
    url.pathname = routes.login;
    // Remember where they were headed so login can return them there.
    if (pathname !== "/") url.searchParams.set("next", pathname);
    return redirectPreservingSession(url, response);
  }

  if (user && isPublicRoute(pathname)) {
    const url = request.nextUrl.clone();
    url.pathname = routes.dashboard;
    url.search = "";
    return redirectPreservingSession(url, response);
  }

  return response;
}

/**
 * Redirect without dropping the refreshed session.
 *
 * A fresh `NextResponse.redirect` carries none of the cookies Supabase just
 * set, so returning one directly discards the rotated token. The browser then
 * replays the stale one, the server component sees no session and sends the
 * user back here -- a redirect loop that renders as a blank page.
 */
function redirectPreservingSession(url: URL, carrier: NextResponse): NextResponse {
  const redirect = NextResponse.redirect(url);
  carrier.cookies.getAll().forEach((cookie) => redirect.cookies.set(cookie));
  return redirect;
}

export const config = {
  matcher: [
    /*
     * Everything except static assets and image files -- those need no session
     * and running the refresh on them would triple the request count.
     */
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|woff2?)$).*)",
  ],
};
