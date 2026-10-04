// Shared meta-description helpers (answer-first SERP snippets).
/**
 * Normalise a raw wiki value:
 *   - unwrap wikilinks  [[Target|Label]] -> Label
 *   - drop template fragments  "Tier 1|location=Undershed Lab" -> "Tier 1"
 *   - strip HTML, stray brackets and bullet markers
 *   - remove "?" placeholders without touching real negatives like "-9%"
 */
export const cl = (v: unknown): string => {
  let s = String(v ?? "")
    .replace(/\[\[[^\]|]*\|([^\]]*)\]\]/g, "$1")
    .replace(/\[[^\]|]*\|([^\]]*)\]/g, "$1")
    .replace(/\[\[([^\]]*)\]\]/g, "$1")
    .split("|")[0]
    .replace(/<[^>]*>/g, "")
    .replace(/[[\]]/g, "")
    .replace(/\*+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (s.includes("?")) {
    s = s.replace(/\?+/g, "").replace(/^[-–—\s,]+|[-–—\s,]+$/g, "").trim();
  }
  return s.replace(/^(?:none|n\/a|-|unknown)$/i, "");
};

/** Kept for readability at call sites that want to be explicit about template fragments. */
export const clean = (v: unknown): string => cl(v);

export const pick = (...vals: unknown[]): string => {
  for (const v of vals) {
    const s = cl(v);
    if (s) return s;
  }
  return "";
};

const isText = (p: unknown): p is string => typeof p === "string" && p.trim().length > 0;

export const clip = (s: string, n = 158): string => {
  const t = String(s ?? "").replace(/\s+/g, " ").replace(/\s+([.,;:!?])/g, "$1").trim();
  if (t.length <= n) return t;
  return t.slice(0, n - 1).replace(/[\s,;:—–-]+$/, "") + "\u2026";
};

/** Only string fragments survive, so callers can write `cond && "…"` inline. */
export const desc = (...parts: unknown[]): string =>
  clip(parts.filter(isText).join(" ").replace(/\s+/g, " ").replace(/\s+\./g, "."));

/** Comma-separated stat run that always ends with a period. */
export const stats = (...parts: unknown[]): string => {
  const kept = parts.filter(isText) as string[];
  if (!kept.length) return "";
  return kept.join(", ").replace(/[\s,;:]+$/, "") + ".";
};

export const introSentence = (intro: unknown, n = 150): string => {
  const s = cl(intro);
  if (!s) return "";
  const m = s.match(/^.{40,}?[.!?](?=\s|$)/);
  return clip(m ? m[0] : s, n);
};

/** Use the summary only when substantial; a short one is worse than a topic sentence. */
export const best = (intro: unknown, fallback: string, minLen = 30, n = 155): string => {
  const s = introSentence(intro, n);
  return s.length >= minLen ? s : fallback;
};

/** Wiki overview pages ("Consumables (Grounded)") are not item entries — skip them. */
export const isIndexPage = (title: unknown): boolean => /\(Grounded\)$/.test(String(title ?? "").trim());
