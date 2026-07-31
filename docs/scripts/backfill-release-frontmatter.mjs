#!/usr/bin/env node
/**
 * Backfills release_date / release_type / description frontmatter across
 * docs/release-notes/infrahub/release-*.mdx.
 *
 *   node scripts/backfill-release-frontmatter.mjs           # write missing fields (idempotent)
 *   node scripts/backfill-release-frontmatter.mjs --check   # exit 1 if any file lacks a field (for CI)
 *
 * - release_date: parsed from the existing HTML <table> ("July 13th, 2026" → 2026-07-13)
 * - release_type: minor for X.Y.0 / legacy X.Y files, security if a "### Security"
 *   section exists, else patch
 * - description: drafted from the file's opening narrative paragraph (minors) or the
 *   first "### Fixed" bullets (patches). DRAFTS ONLY — spot-check recent versions by hand.
 *
 * The `breaking: true` flag is set by hand on releases that carry a
 * Breaking-changes section; this script never adds or removes it.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const DIR = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "docs", "release-notes", "infrahub");
const CHECK = process.argv.includes("--check");
const MONTHS = ["january","february","march","april","may","june","july","august","september","october","november","december"];

const parseDate = (body) => {
  const m = body.match(/Release Date<\/th>\s*<td>([^<]+)</i);
  if (!m) return null;
  const d = m[1].match(/([A-Za-z]+)\s+(\d+)\w*,?\s+(\d{4})/);
  if (!d) return null;
  const month = MONTHS.findIndex((name) => name.startsWith(d[1].toLowerCase())) + 1;
  if (!month) return null;
  return `${d[3]}-${String(month).padStart(2, "0")}-${String(d[2]).padStart(2, "0")}`;
};

// Keep `_` — stripping it mangles the snake_case identifiers that changelog
// entries quote in backticks (`order_weight` → "orderweight"), which both reads
// wrong in the feed and trips Vale's spelling check.
const stripMd = (s) =>
  s.replace(/\[([^\]]+)\]\([^)]*\)/g, "$1").replace(/[*`#]/g, "").replace(/\s+/g, " ").trim();

const firstSentences = (text, max = 220) => {
  const out = [];
  for (const s of text.split(/(?<=[.!?])\s+/)) {
    if (out.join(" ").length + s.length > max && out.length) break;
    out.push(s);
    if (out.length === 2) break;
  }
  return out.join(" ");
};

const draftDescription = (body, type) => {
  const afterTable = body.split(/<\/table>/i)[1] ?? body;
  if (type === "minor") {
    const para = afterTable
      .split(/\n{2,}/)
      .map((p) => p.trim())
      .find((p) => p && !p.startsWith("#") && !p.startsWith("<") && !p.startsWith("!") && p.length > 60);
    if (para) return firstSentences(stripMd(para));
  }
  // Patch/security: summarize the first bullets under ### Security / ### Fixed / ### Added.
  const section = afterTable.match(/###\s+(Security|Fixed|Added)\s*\n([\s\S]*?)(?=\n###|\n##|$)/);
  if (section) {
    const bullets = section[2]
      .split("\n")
      .filter((l) => l.trim().startsWith("- "))
      .map((l) => stripMd(l.trim().slice(2)).split(/(?<=[.!?])\s/)[0])
      .slice(0, 2);
    if (bullets.length) {
      const prefix = section[1] === "Security" ? "Security release: " : "";
      return firstSentences(prefix + bullets.join(" "), 220);
    }
  }
  return "Bug-fix release.";
};

let missing = 0;
for (const file of fs.readdirSync(DIR).sort()) {
  const m = file.match(/^release-(\d+)_(\d+)(?:_(\d+))?\.mdx$/);
  if (!m) continue;
  const full = path.join(DIR, file);
  const src = fs.readFileSync(full, "utf8");
  const fm = src.match(/^---\n([\s\S]*?)\n---\n/);
  if (!fm) {
    if (CHECK) { console.error(`MISSING frontmatter: ${file} → no frontmatter block`); missing++; }
    else console.warn(`SKIP (no frontmatter): ${file}`);
    continue;
  }

  const has = (k) => new RegExp(`^${k}:`, "m").test(fm[1]);
  const body = src.slice(fm[0].length);
  const type = m[3] === undefined || m[3] === "0"
    ? "minor"
    : /^###\s+Security/m.test(body) ? "security" : "patch";

  const additions = [];
  if (!has("release_date")) {
    const date = parseDate(body);
    if (date) additions.push(`release_date: ${date}`);
    else console.warn(`WARN no date parsed: ${file}`);
  }
  if (!has("release_type")) additions.push(`release_type: ${type}`);
  if (!has("description")) {
    // Serialize via JSON.stringify so backslashes/quotes in the drafted text
    // stay valid YAML (a plain quoted interpolation would only escape `"`).
    additions.push(`description: ${JSON.stringify(draftDescription(body, type))}`);
  }

  if (additions.length === 0) continue;
  if (CHECK) { console.error(`MISSING frontmatter: ${file} → ${additions.map((a) => a.split(":")[0]).join(", ")}`); missing++; continue; }

  const next = `---\n${fm[1]}\n${additions.join("\n")}\n---\n${body}`;
  fs.writeFileSync(full, next);
  console.log(`updated ${file}: +${additions.map((a) => a.split(":")[0]).join(", +")}`);
}
if (CHECK && missing) process.exit(1);
