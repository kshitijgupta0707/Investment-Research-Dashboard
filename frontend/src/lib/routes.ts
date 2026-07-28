/** Every path in the app, named once. */
export const routes = {
  login: "/login",
  signup: "/signup",
  dashboard: "/dashboard",
  research: "/research",
  reports: "/reports",
  watchlist: "/watchlist",
  organization: "/organization",
} as const;

/** Routes reachable while signed out. Everything else redirects to login. */
export const publicRoutes: readonly string[] = [routes.login, routes.signup];

export function isPublicRoute(pathname: string): boolean {
  return publicRoutes.some((route) => pathname === route || pathname.startsWith(`${route}/`));
}
