import { NextResponse, type NextRequest } from "next/server";

/*
 * Next.js 16 `proxy.ts` (the renamed middleware.ts) for a two-role personal app.
 * Copy to the repo root; supply verify()/tokenFor()/timingSafeEqual() from lib/auth.ts
 * (HMAC-signed cookie "<role>.<expiry>.<sig>" via WebCrypto, which runs in the proxy runtime).
 *
 *   /?key=<LEARNER_KEY>          private link: sets the learner cookie and serves the app WITH the key
 *                                 still in the URL (no redirect). iOS "Add to Home Screen" saves the
 *                                 current URL, and home-screen web apps don't reliably share the
 *                                 browser's cookies, so stripping the key locks the icon out.
 *   /, /api/*                     learner OR admin
 *   /admin/*, /api/admin/*        admin only. Everyone else gets a plain 404 (NOT 401/403), so the
 *                                 recipient never learns a dashboard exists. Route handlers repeat
 *                                 the check (defense in depth) and also answer 404.
 *   /admin/login, /api/admin/login   public password form
 *   /api/cron/*                   Vercel cron, checked in the handler with CRON_SECRET
 *   /api/version                  public: only reveals the deployment id (used by auto-update)
 */
import { ADMIN_COOKIE, COOKIE_OPTS, LEARNER_COOKIE, timingSafeEqual, tokenFor, verify } from "@/lib/auth";

export async function proxy(req: NextRequest) {
  const { pathname, searchParams } = req.nextUrl;
  if (pathname.startsWith("/api/cron/") || pathname === "/api/version") return NextResponse.next();
  if (pathname === "/admin/login" || pathname === "/api/admin/login") return NextResponse.next();

  const isAdmin = await verify(req.cookies.get(ADMIN_COOKIE)?.value, "admin");
  if (pathname.startsWith("/admin") || pathname.startsWith("/api/admin")) {
    if (isAdmin) return NextResponse.next();
    return new NextResponse("Not found", { status: 404, headers: { "content-type": "text/plain" } });
  }

  const key = searchParams.get("key");
  if (pathname === "/" && key) {
    const expected = process.env.LEARNER_KEY ?? "";
    if (expected && timingSafeEqual(key, expected)) {
      const res = NextResponse.next(); // keep ?key= in the URL for Add to Home Screen
      res.cookies.set(LEARNER_COOKIE, await tokenFor("learner"), COOKIE_OPTS);
      return res;
    }
    const url = req.nextUrl.clone();
    url.pathname = "/locked";
    url.search = "";
    return NextResponse.rewrite(url);
  }

  const ok = isAdmin || (await verify(req.cookies.get(LEARNER_COOKIE)?.value, "learner"));
  if (ok) return NextResponse.next();
  if (pathname.startsWith("/api/")) return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  const url = req.nextUrl.clone();
  url.pathname = "/locked";
  url.search = "";
  return pathname === "/locked" ? NextResponse.next() : NextResponse.rewrite(url);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|icon.png|apple-icon.png|manifest.webmanifest|locked).*)"],
};
