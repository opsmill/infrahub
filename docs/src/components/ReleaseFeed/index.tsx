/**
 * <ReleaseFeed/> — release feed for /release-notes/infrahub.
 * Full detail for the newest `detailedLines` release lines, compact rows for
 * earlier ones. Reads global data from plugins/release-notes-data.js.
 */
import React from "react";
import Link from "@docusaurus/Link";
import { usePluginData } from "@docusaurus/useGlobalData";
import styles from "./styles.module.css";

type Release = {
  version: string;
  line: string;
  major: number;
  minor: number;
  patch: number | null;
  date: string | null;
  type: "minor" | "patch" | "security";
  description: string;
  breaking: boolean;
  permalink: string;
};

const fmtDate = (iso: string | null, month: "long" | "short" = "long") =>
  iso
    ? new Date(`${iso}T00:00:00`).toLocaleDateString("en-US", { year: "numeric", month, day: "numeric" })
    : "";

/** Fully-expanded group: X.Y.0 hero first, then updates in chronological (ascending) order. */
function LineGroup({ line, releases }: { line: string; releases: Release[] }) {
  const base = releases.find((r) => r.patch === 0 || r.patch === null) ?? releases[0];
  const updates = releases.filter((r) => r !== base).sort((a, b) => (a.patch ?? 0) - (b.patch ?? 0));
  return (
    <section className={styles.group}>
      <div className={styles.groupHead}>
        <h2>{line}</h2>
        <span className={styles.featureBadge}>Feature release</span>
      </div>
      <Link to={base.permalink} className={styles.heroRow}>
        <div className={styles.rowHead}>
          <span className={styles.heroVersion}>{base.version}</span>
          {base.breaking && <span className={styles.breakingChip}>Breaking changes</span>}
          <span className={styles.date}>{fmtDate(base.date)}</span>
        </div>
        {base.description && <p className={styles.heroSummary}>{base.description}</p>}
      </Link>
      <div className={styles.updates}>
        {updates.map((r) => (
          <Link key={r.version} to={r.permalink} className={styles.updateRow}>
            <span className={styles.bullet} />
            <div className={styles.rowHead}>
              <span className={styles.updateVersion}>{r.version}</span>
              {r.breaking && <span className={styles.breakingChip}>Breaking</span>}
              <span className={styles.date}>{fmtDate(r.date)}</span>
            </div>
            {r.description && <p className={styles.summary}>{r.description}</p>}
          </Link>
        ))}
      </div>
    </section>
  );
}

/** Compact row for older lines: version · description · date. */
function EarlierRow({ base }: { base: Release }) {
  return (
    <Link to={base.permalink} className={styles.earlierRow}>
      <span className={styles.earlierVersion}>{base.line}</span>
      <span className={styles.earlierSummary}>{base.description}</span>
      <span className={styles.date}>{fmtDate(base.date, "short")}</span>
    </Link>
  );
}

/** Newest `detailedLines` version lines fully expanded; the rest as compact rows. */
export default function ReleaseFeed({ detailedLines = 2 }: { detailedLines?: number }) {
  const { releases } = usePluginData("release-notes-data") as { releases: Release[] };
  const lines: string[] = [];
  for (const r of releases) if (!lines.includes(r.line)) lines.push(r.line); // newest line first
  const detailed = lines.slice(0, detailedLines);
  const earlier = lines.slice(detailedLines);
  return (
    <div className={styles.feed}>
      <h1 className={styles.title}>Infrahub release notes</h1>
      {detailed.map((line) => (
        <LineGroup key={line} line={line} releases={releases.filter((r) => r.line === line)} />
      ))}
      <section className={styles.group}>
        <div className={styles.earlierHead}>
          <h2>Earlier releases</h2>
        </div>
        {earlier.map((line) => {
          const rs = releases.filter((r) => r.line === line);
          const base = rs.find((r) => r.patch === 0 || r.patch === null) ?? rs[rs.length - 1];
          return <EarlierRow key={line} base={base} />;
        })}
      </section>
    </div>
  );
}
