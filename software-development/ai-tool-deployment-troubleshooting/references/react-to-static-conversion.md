# React → static HTML conversion, in detail

Merged in from `Vercel Deployment Fixes` (2026-09-27). SKILL.md §3 gives the
short version; this is the full procedure and the decision table.

## Diagnose an architecture mismatch

```bash
wc -l package.json    # >40 lines: complex React setup; working tools are <15
ls src/               # React components
ls api/*.ts           # TypeScript API routes (working tools use api/*.js)
```

Build logs showing `npm error Invalid Version`, `Function Runtimes must have a
valid version`, or failure during `npm install` after vercel.json and API
routes have already been fixed point here.

## Two paths

**Path A: fix the React deployment** when React features are essential
(complex state, many components), the team prefers React, and there's time to
debug. Steps: fix the vercel.json runtime, update package.json dependencies,
resolve TypeScript errors, untangle npm conflicts.

**Path B: convert to static HTML** (recommended for AI tools) when the UI is a
form → API call → results, build errors persist after config fixes, and a
reliable deploy is needed now.

| Aspect | React build | Static HTML |
|---|---|---|
| Build process | webpack, babel, TypeScript | none |
| Dependencies | 20+ packages | 1–3 |
| Deploy speed | build + deploy | direct |
| Failure points | build deps, compilation | code syntax only |
| Debugging | through build tooling | directly in the browser |
| Maintenance | dependency churn | minimal |

**Stay on React** with complex cross-component state, websockets/real-time
updates, rich interaction beyond forms, strong team React expertise, or a
large working codebase.

## Conversion steps

1. **Back up**: `package.json`, `vercel.json`, `src/`.
2. **Copy a working reference**: compare its file tree, package.json and
   vercel.json with the failing project.
3. **JSX → HTML**: keep the layout and classes, load Tailwind from the CDN,
   wire handlers with `addEventListener`:

```html
<div class="container mx-auto px-4 py-8">
  <div class="bg-white rounded-lg shadow p-6">
    <textarea id="inputText" class="w-full p-4 border rounded"></textarea>
    <button id="processBtn" class="bg-blue-500 text-white px-4 py-2 rounded">Process</button>
  </div>
</div>
<script>
document.getElementById('processBtn').addEventListener('click', handleSubmit);
</script>
```

4. **TypeScript API → JavaScript**: rename `.ts` → `.js`, drop the
   `VercelRequest`/`VercelResponse` types and interfaces, keep the logic.
5. **Minimal config**:

```json
{
  "name": "ai-tool-name",
  "version": "1.0.0",
  "private": true,
  "dependencies": { "openai": "^4.0.0" }
}
```

```json
{
  "version": 2,
  "buildCommand": "",
  "outputDirectory": ".",
  "functions": { "api/process.js": { "maxDuration": 30 } }
}
```

## Preserve everything

- UI: validation, loading and error states, results with copy, responsive
  layout.
- Logic: rate limiting, OpenAI integration, demo fallback, error handling.
- Monetization: AdSense, cookie consent, privacy and terms pages.
- SEO: meta tags, structured data, robots.txt, sitemap.xml, ads.txt.

## Post-conversion checklist

- [ ] Every original feature works identically
- [ ] API routes accept and return the same shapes
- [ ] Rate limiting and error handling preserved
- [ ] AdSense and compliance intact; mobile layout intact
- [ ] SEO elements carried over
- [ ] Deploy succeeds and production testing passes

## Worked case: Legal Translator AI

React build failing with `Invalid Version`, plus a corrupted TypeScript line
(`const openaiApiKey=proces...KEY;`). Fixing vercel.json and dependencies
didn't help. Converting to static HTML (44-line package.json → 8 lines) kept
every feature and deployed first time, with no build issues since.
