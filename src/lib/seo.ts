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

/**
 * `"X is a Tier 3 Axe."` / `"X is a Tier 2 Trinket in Grounded."` — a wiki lead
 * sentence that only restates the item's identity adds nothing the stats line
 * has not already said, and it pushes real numbers past the 158-char cap.
 * A lead is kept only when it is long enough AND carries a relation the stats
 * lack (source, use, material, behaviour).
 */
const RESTATES_ONLY =
  /\b(of|by|from|with|that|which|used|found|obtained|drops?|requires?|grants?|unlocks?|made|variant|being|contain|leads?)\b/i;

const NOISE_LEAD = /^This is a (?:more advanced covering of the loot-table|complete list)/i;

const isRestatement = (s: string): boolean => {
  if (NOISE_LEAD.test(s)) return true; // a wiki maintenance note, not an item description
  if (s.length >= 90) return false; // long enough to be saying something
  if (!/^(?:the\s+)?.+?\s+(?:is|are)\s+(?:a|an|the)\b/i.test(s)) return false; // not a definition
  // (title may contain dots: "O.R.C. Cricket is a creature...")
  return !RESTATES_ONLY.test(s);
};

/** Use the summary only when substantial AND informative; a restatement is worse than none. */
export const best = (intro: unknown, fallback: string, minLen = 30, n = 155): string => {
  const s = introSentence(intro, n);
  if (s && isRestatement(s)) return "";
  return s.length >= minLen ? s : fallback;
};

/** Wiki overview pages ("Consumables (Grounded)") are not item entries — skip them. */
export const isIndexPage = (title: unknown): boolean => /\(Grounded\)$/.test(String(title ?? "").trim());


/**
 * Tail clause for the SERP snippet.
 * A wiki lead sentence that only restates identity ("X is a Tier 3 Axe.") is
 * dropped rather than padding the snippet with noise. When dropping it would
 * leave the snippet too thin, the site's own prose lead fills the gap.
 */
export const tail = (summary: unknown, prose: any, prefix: string, fallback: string, n = 155): string => {
  const s = introSentence(summary, n);
  if (s && !isRestatement(s)) return s; // the wiki lead carries extra facts
  if (cl(prefix).length >= 70) return ""; // the stats run already fills the snippet
  const lead = introSentence(prose && prose.lead, n);
  if (lead && lead.length >= 40 && !isRestatement(lead)) return lead; // our own prose, when it says something
  return fallback; // dataset too thin for a real sentence — the topic line still fills the snippet
};
