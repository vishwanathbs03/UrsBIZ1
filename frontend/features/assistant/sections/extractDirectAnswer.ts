/**
 * SPRINT AI-6 — Trust-first visual UI. Pure extractor that
 * surfaces the first 1-3 sentences from a chat message so the
 * new `DirectAnswer` component can render the 10-second-read
 * header.
 *
 * Mirrors the backend ``_extract_direct_answer`` so client-side
 * derived answers (for legacy rows where the server didn't
 * stamp ``direct_answer``) read the same way as server-stamped
 * ones.
 *
 * The function is pure: same input → same output. No mutation.
 * No I/O.
 */

/**
 * Maximum number of sentences to surface. The brief says 1-3
 * sentences; 3 is the upper bound.
 */
export const DIRECT_ANSWER_MAX_SENTENCES = 3;

/**
 * Hard character cap. The backend truncates at 600; the
 * frontend mirror is defensive — if the server-stamped value
 * is somehow longer, we don't blow the layout.
 */
export const DIRECT_ANSWER_MAX_CHARS = 600;

const SENTENCE_BOUNDARY = /(?<=[.!?])\s+/;
const MARKDOWN_PREFIX = /^[ \t\-*>#]+/;

/**
 * Extract the first 1-3 sentences from a prose block.
 *
 * Returns ``null`` when the input is empty / non-string /
 * sentence-less. The split is on sentence-ending punctuation
 * (`.`, `!`, `?`) followed by whitespace. Markdown list and
 * blockquote markers are stripped so the snippet reads as
 * plain prose.
 *
 * @param prose The full assistant prose / body / executive
 * summary. May be ``null`` or ``undefined`` — returns
 * ``null`` in that case.
 */
export function extractDirectAnswer(
  prose: string | null | undefined,
): string | null {
  if (!prose || typeof prose !== "string") {
    return null;
  }
  const trimmed = prose.trim();
  if (!trimmed) {
    return null;
  }
  const parts = trimmed.split(SENTENCE_BOUNDARY);
  const cleaned: string[] = [];
  for (const part of parts) {
    const stripped = part.replace(MARKDOWN_PREFIX, "").trim();
    if (!stripped) {
      continue;
    }
    cleaned.push(stripped);
    if (cleaned.length >= DIRECT_ANSWER_MAX_SENTENCES) {
      break;
    }
  }
  if (cleaned.length === 0) {
    return null;
  }
  let out = cleaned.join(" ");
  if (out.length > DIRECT_ANSWER_MAX_CHARS) {
    out = out.slice(0, DIRECT_ANSWER_MAX_CHARS - 3).trimEnd() + "...";
  }
  return out;
}

/**
 * Resolve the direct answer for a message using the full
 * fallback ladder:
 *
 *   1. ``message.direct_answer`` (server-stamped, AI-6)
 *   2. ``groundedPayload.executive_summary`` (H7.8C grounded path)
 *   3. ``consultant.body`` (H4 local deterministic path)
 *   4. ``message.content`` (legacy / typed-body path)
 *
 * Each source is passed through ``extractDirectAnswer`` so the
 * output is always 1-3 sentences, never the full prose.
 */
export function resolveDirectAnswer(input: {
  directAnswer?: string | null;
  groundedSummary?: string | null;
  consultantBody?: string | null;
  content?: string | null;
}): string | null {
  return (
    extractDirectAnswer(input.directAnswer) ??
    extractDirectAnswer(input.groundedSummary) ??
    extractDirectAnswer(input.consultantBody) ??
    extractDirectAnswer(input.content)
  );
}