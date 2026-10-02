"use client";
/*
 * Silent auto-update for a Vercel-hosted home-screen web app (verified on production, Oct 2026).
 *
 * Wiring (3 pieces):
 *  1. next.config.ts:
 *       const BUILD_ID = process.env.VERCEL_DEPLOYMENT_ID || `local-${Date.now()}`;
 *       export default { env: { NEXT_PUBLIC_BUILD_ID: BUILD_ID } };
 *     -> the same id is baked into the server AND the client bundle at build time.
 *  2. app/api/version/route.ts (PUBLIC in proxy.ts; it only reveals the deployment id):
 *       export const dynamic = "force-dynamic";
 *       export function GET() {
 *         return Response.json({ build: process.env.NEXT_PUBLIC_BUILD_ID ?? "" },
 *           { headers: { "cache-control": "no-store, max-age=0" } });
 *       }
 *  3. In the main client component (state must already persist in localStorage/server):
 *       useAutoUpdate(!voiceOpen && !busy && !input.trim(), () => flushPendingEvents());
 *
 * Behavior: checks on visibilitychange/pageshow/focus (throttled 20s) and every 10 min.
 * Reloads only when safe (no voice call, no reply in flight, nothing typed); if an update
 * arrives mid-use it applies as soon as the app goes idle. sessionStorage loop guard =
 * at most one reload attempt per new build. Test with scripts/update-check.py.
 */
import { useEffect, useRef } from "react";

const BUILD = process.env.NEXT_PUBLIC_BUILD_ID ?? "";
const MIN_GAP_MS = 20_000;

export function useAutoUpdate(isSafe: boolean, beforeReload: () => Promise<unknown>) {
  const newer = useRef(false);
  const lastCheck = useRef(0);
  const safe = useRef(isSafe);
  const before = useRef(beforeReload);
  safe.current = isSafe;
  before.current = beforeReload;

  const reload = async () => {
    newer.current = false;
    try {
      await before.current();
    } catch {}
    location.reload();
  };
  const reloadRef = useRef(reload);
  reloadRef.current = reload;

  useEffect(() => {
    if (!BUILD) return;
    const check = async () => {
      if (document.visibilityState !== "visible") return;
      if (Date.now() - lastCheck.current < MIN_GAP_MS) return;
      lastCheck.current = Date.now();
      try {
        const r = await fetch("/api/version", { cache: "no-store" });
        const { build } = (await r.json()) as { build?: string };
        if (!build || build === BUILD) return;
        if (sessionStorage.getItem("app.reloadedFor") === build) return; // loop guard
        sessionStorage.setItem("app.reloadedFor", build);
        newer.current = true;
        if (safe.current) void reloadRef.current();
      } catch {}
    };
    const onWake = () => void check();
    document.addEventListener("visibilitychange", onWake);
    window.addEventListener("pageshow", onWake);
    window.addEventListener("focus", onWake);
    const timer = setInterval(check, 10 * 60_000);
    void check();
    return () => {
      document.removeEventListener("visibilitychange", onWake);
      window.removeEventListener("pageshow", onWake);
      window.removeEventListener("focus", onWake);
      clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (isSafe && newer.current) void reloadRef.current();
  }, [isSafe]);
}
