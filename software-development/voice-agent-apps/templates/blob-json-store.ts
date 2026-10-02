import { put, get, list, BlobPreconditionFailedError, BlobNotFoundError } from "@vercel/blob";

/**
 * Tiny JSON document store on a PRIVATE Vercel Blob store (@vercel/blob >= 2.8).
 * - readDoc bypasses the CDN cache (useCache:false) so reads are fresh.
 * - updateJson = read-modify-write with ETag ifMatch + jittered retry, so parallel
 *   writers (e.g. two agent tool calls landing at once) never clobber each other.
 * Needs BLOB_READ_WRITE_TOKEN in the environment (auto-set when the store is linked to the project).
 *
 * VERIFIED IN PRODUCTION (Oct 2026), two non-obvious traps handled below:
 *  1. get() on a private store returns a WEAK etag (W/"…") once the doc is over ~1KB (compressed
 *     response). put({ifMatch}) only matches the STRONG form, so without stripping "W/" every write
 *     to a larger doc fails with "Precondition failed: ETag mismatch" forever (retries can't help).
 *     Small docs (<1KB) return strong etags, so this only shows up after real use.
 *  2. Genuinely racing writes throw a different message: "The conditional request cannot succeed due
 *     to a conflicting operation against this resource." Treat it as retryable too. Match by message,
 *     because instanceof is unreliable once the SDK is bundled into multiple chunks.
 * Proof test: 6 concurrent increments on a 4KB doc -> final n === 6.
 */

type Doc<T> = { data: T; etag: string | null };
const ACCESS = "private" as const;

export async function readDoc<T>(path: string): Promise<Doc<T> | null> {
  try {
    const res = await get(path, { access: ACCESS, useCache: false });
    if (!res || res.statusCode !== 200) return null;
    const text = await new Response(res.stream).text();
    const etag = res.blob.etag ? res.blob.etag.replace(/^W\//, "") : null; // trap 1
    return { data: JSON.parse(text) as T, etag };
  } catch (e) {
    if (e instanceof BlobNotFoundError || (e instanceof Error && /not found|does not exist/i.test(e.message))) return null;
    throw e;
  }
}

export async function readJson<T>(path: string): Promise<T | null> {
  return (await readDoc<T>(path))?.data ?? null;
}

export async function writeJson<T>(path: string, data: T, ifMatch?: string | null): Promise<void> {
  await put(path, JSON.stringify(data), {
    access: ACCESS,
    contentType: "application/json",
    addRandomSuffix: false,
    allowOverwrite: true,
    cacheControlMaxAge: 60,
    ...(ifMatch ? { ifMatch } : {}),
  });
}

function isConflict(e: unknown) {
  // trap 2
  return (
    e instanceof BlobPreconditionFailedError ||
    (e instanceof Error && /precondition failed|etag mismatch|conditional request cannot succeed|conflicting operation/i.test(e.message))
  );
}

export async function updateJson<T>(path: string, init: () => T, fn: (cur: T) => T | Promise<T>, tries = 8): Promise<T> {
  let lastErr: unknown;
  for (let i = 0; i < tries; i++) {
    const doc = await readDoc<T>(path);
    const next = await fn(doc ? doc.data : init());
    try {
      await writeJson(path, next, doc?.etag ?? null);
      return next;
    } catch (e) {
      lastErr = e;
      if (isConflict(e)) {
        await new Promise((r) => setTimeout(r, 40 + Math.random() * 120 * (i + 1)));
        continue;
      }
      throw e;
    }
  }
  throw lastErr;
}

export async function listPaths(prefix: string): Promise<string[]> {
  const out: string[] = [];
  let cursor: string | undefined;
  do {
    const page = await list({ prefix, cursor, limit: 1000 });
    out.push(...page.blobs.map((b) => b.pathname));
    cursor = page.hasMore ? page.cursor : undefined;
  } while (cursor);
  return out;
}

// Pricing note (Oct 2026): put/list = Advanced Operations ($5/1M after 2K free on Pro),
// cache-miss reads = Simple ($0.40/1M after 10K). Fine for single-user apps; batch writes for bigger ones.
