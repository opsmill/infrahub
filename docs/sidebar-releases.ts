/**
 * Generates the grouped Infrahub release-notes sidebar.
 * Globs docs/release-notes/infrahub/release-*.mdx, parses versions from
 * filenames, and returns one collapsed category per minor line (newest line
 * first, releases inside a line in chronological ascending order).
 */
import * as fs from 'fs';
import * as path from 'path';
import type { SidebarItemConfig } from '@docusaurus/plugin-content-docs/src/sidebars/types';

const RELEASE_DIR = path.join(__dirname, 'docs', 'release-notes', 'infrahub');
const RELEASE_RE = /^release-(\d+)_(\d+)(?:_(\d+))?\.mdx$/;

type Release = { major: number; minor: number; patch: number | null; id: string };

function readReleases(): Release[] {
  return fs
    .readdirSync(RELEASE_DIR)
    .map((f) => {
      const m = f.match(RELEASE_RE);
      if (!m) return null;
      return {
        major: Number(m[1]),
        minor: Number(m[2]),
        patch: m[3] === undefined ? null : Number(m[3]),
        id: `release-notes/infrahub/${f.replace(/\.mdx$/, '')}`,
      };
    })
    .filter((r): r is Release => r !== null);
}

/** One collapsed category per minor line ("1.10 release", "1.9 release", …), newest first. */
export function generateInfrahubReleaseSidebar(): SidebarItemConfig[] {
  const byLine = new Map<string, Release[]>();
  for (const r of readReleases()) {
    const line = `${r.major}.${r.minor}`;
    (byLine.get(line) ?? byLine.set(line, []).get(line)!).push(r);
  }

  const lines = [...byLine.keys()].sort((a, b) => {
    const [am, an] = a.split('.').map(Number);
    const [bm, bn] = b.split('.').map(Number);
    return bm - am || bn - an; // newest line first
  });

  return lines.map((line) => {
    const releases = byLine
      .get(line)!
      .sort((a, b) => (a.patch ?? 0) - (b.patch ?? 0)); // chronological ascending

    // Legacy single-file lines (release-0_6.mdx …): plain doc link, no category.
    if (releases.length === 1 && releases[0].patch === null) {
      return { type: 'doc', id: releases[0].id, label: `${line} release` } as SidebarItemConfig;
    }

    const base = releases.find((r) => r.patch === 0 || r.patch === null);
    return {
      type: 'category',
      label: `${line} release`,
      collapsed: true,
      collapsible: true,
      // Clicking the line opens its X.Y.0 release (the narrative feature release).
      ...(base ? { link: { type: 'doc', id: base.id } } : {}),
      items: releases.map((r) => ({
        type: 'doc' as const,
        id: r.id,
        label: r.patch === null ? line : `${line}.${r.patch}`,
      })),
    } as SidebarItemConfig;
  });
}
