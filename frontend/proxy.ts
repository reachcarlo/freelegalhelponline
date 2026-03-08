import { NextRequest, NextResponse } from "next/server";

/**
 * Next.js proxy for route protection (formerly middleware).
 *
 * Checks cookie presence only (fast, no JWT validation).
 * The actual JWT validation happens server-side when the API is called.
 * This is defense-in-depth, not security-through-obscurity.
 */
export function proxy(request: NextRequest) {
  const accessToken = request.cookies.get("access_token");

  if (!accessToken) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", request.nextUrl.pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/tools/litigagent",
    "/tools/litigagent/:path*",
    "/tools/discovery",
    "/tools/discovery/:path*",
  ],
};
