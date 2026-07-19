/**
 * Build-time plugin: scans release-notes frontmatter into global plugin data.
 * Registered in docusaurus.config.ts; consumed via
 * usePluginData("release-notes-data") in <ReleaseFeed/>.
 */
const fs = require("fs");
const path = require("path");

// Minimal parser for the flat `key: value` frontmatter used by release files
// (see scripts/backfill-release-frontmatter.mjs); gray-matter is not a
// dependency of this site.
function parseFrontmatter(src) {
  const m = src.match(/^---\n([\s\S]*?)\n---\n/);
  if (!m) return {};
  const data = {};
  for (const line of m[1].split("\n")) {
    const kv = line.match(/^([A-Za-z_]+):\s*(.*)$/);
    if (!kv) continue;
    let value = kv[2].trim();
    if (value.startsWith('"') && value.endsWith('"')) value = value.slice(1, -1);
    if (value === "true") value = true;
    else if (value === "false") value = false;
    data[kv[1]] = value;
  }
  return data;
}

module.exports = function releaseNotesData() {
  return {
    name: "release-notes-data",
    async contentLoaded({ actions }) {
      const dir = path.join(__dirname, "..", "docs", "release-notes", "infrahub");
      const releases = fs
        .readdirSync(dir)
        .map((file) => {
          const m = file.match(/^release-(\d+)_(\d+)(?:_(\d+))?\.mdx$/);
          if (!m) return null;
          const data = parseFrontmatter(fs.readFileSync(path.join(dir, file), "utf8"));
          return {
            version: m[3] === undefined ? `${m[1]}.${m[2]}` : `${m[1]}.${m[2]}.${m[3]}`,
            line: `${m[1]}.${m[2]}`,
            major: +m[1],
            minor: +m[2],
            patch: m[3] === undefined ? null : +m[3],
            date: data.release_date ?? null, // ISO string
            type: data.release_type ?? "patch", // minor | patch | security
            description: data.description ?? "",
            breaking: data.breaking === true,
            permalink: `/release-notes/infrahub/${file.replace(/\.mdx$/, "")}`,
          };
        })
        .filter(Boolean)
        .sort((a, b) => b.major - a.major || b.minor - a.minor || (b.patch ?? 0) - (a.patch ?? 0));
      actions.setGlobalData({ releases });
    },
  };
};
