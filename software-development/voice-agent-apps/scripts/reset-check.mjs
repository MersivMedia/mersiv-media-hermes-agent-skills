// Exercise the real "Reset for <learner>" path on production (as admin), then confirm the learner
// starts from zero and the previous period is archived but still readable.
// WARNING: performs a REAL reset. Run before hand-off, never after the learner has started.
// Usage: BASE=https://<app>.vercel.app SECRETS=~/.hermes/data/<app>/ node reset-check.mjs "<new period label>"
// Assumes: POST /api/admin/period {action:"reset",label,confirm:"RESET"}, GET /api/home?lang=..,
//          /admin?period=<id> renders "archived period" text, cookies klt_learner / klt_admin.
import { readFileSync } from "node:fs";
import { homedir } from "node:os";
const BASE = process.env.BASE;
const S = (process.env.SECRETS || "").replace(/^~/, homedir()).replace(/\/?$/, "/");
if (!BASE || !S) throw new Error("set BASE and SECRETS");
const ok = (c, m) => { console.log(`${c ? "PASS" : "FAIL"}  ${m}`); if (!c) process.exitCode = 1; };
const ck = (r) => (r.headers.getSetCookie?.() ?? []).map((c) => c.split(";")[0]).join("; ");
const label = process.argv[2] || "Owner testing";
const LANG = process.env.LANG_CODE || "es";

let r = await fetch(`${BASE}/api/admin/login`, { method: "POST", body: new URLSearchParams({ password: readFileSync(S + "admin_password", "utf8").trim() }), redirect: "manual" });
const admin = ck(r);
r = await fetch(`${BASE}/?key=${encodeURIComponent(readFileSync(S + "learner_key", "utf8").trim())}`, { redirect: "manual" });
const learner = ck(r);

const before = await (await fetch(`${BASE}/api/home?lang=${LANG}`, { headers: { cookie: learner } })).json();
console.log(`before: period ${before.period}, ${before.progress.learned} learned`);

const post = (cookie, body) => fetch(`${BASE}/api/admin/period`, { method: "POST", headers: { cookie, "content-type": "application/json" }, body: JSON.stringify(body) });
r = await post(learner, { action: "reset", label, confirm: "RESET" });
ok(r.status === 404, `learner cannot reset (${r.status})`);
r = await post(admin, { action: "reset", label, confirm: "nope" });
ok(r.status === 400, "reset without typing RESET is refused");
r = await post(admin, { action: "reset", label, confirm: "RESET" });
const meta = (await r.json()).meta;
ok(r.status === 200 && meta.currentPeriod !== before.period, `reset ok -> new period "${label}"`);

const after = await (await fetch(`${BASE}/api/home?lang=${LANG}`, { headers: { cookie: learner } })).json();
ok(after.period === meta.currentPeriod && after.progress.learned === 0 && after.recent.length === 0, `learner starts fresh (${after.progress.learned} learned)`);
const old = meta.periods.find((p) => p.id === before.period);
ok(!!old?.endedAt, `old period "${old?.label}" archived`);
r = await fetch(`${BASE}/admin?period=${before.period}`, { headers: { cookie: admin } });
ok(r.status === 200 && (await r.text()).includes("archived period"), "archived period still viewable");
