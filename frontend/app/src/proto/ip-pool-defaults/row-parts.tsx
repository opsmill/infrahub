import React from "react";

import { Link } from "@/shared/components/ui/link";

import type { ProtoPool } from "./data";
import type { DefaultEntry } from "./shared";

export function Dot({ inline }: { inline?: boolean }) {
  return (
    <span className={inline ? "mx-1.5 text-foreground-muted/60" : "text-foreground-muted/60"} aria-hidden>
      ·
    </span>
  );
}

export function Divider() {
  return <span className="mx-1 h-4 w-px shrink-0 self-center bg-border-strong" aria-hidden />;
}

export function Namespace({ pool, className }: { pool: ProtoPool; className?: string }) {
  return (
    <span className="text-foreground-muted">
      In namespace{" "}
      <Link to="/ipam" className={className ?? "font-medium text-foreground"}>
        {pool.namespace}
      </Link>
    </span>
  );
}

interface PhraseProps {
  entry: DefaultEntry;
  short?: boolean;
  lowercase?: boolean;
}

export function Phrase({ entry, short, lowercase }: PhraseProps) {
  const label = lowercase ? entry.label.toLowerCase() : entry.label;

  if (entry.value === null) {
    return (
      <span className="text-foreground-muted">
        {label} {entry.fallbackPhrase}
      </span>
    );
  }

  return (
    <span className="text-foreground-muted">
      {label} {short ? "to" : "defaults to"} <span className="text-foreground">{entry.value}</span>
    </span>
  );
}

export function Joined({ children, inline }: { children: React.ReactNode[]; inline?: boolean }) {
  return (
    <>
      {children.map((child, index) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: static prototype list
        <React.Fragment key={index}>
          {index > 0 && <Dot inline={inline} />}
          {child}
        </React.Fragment>
      ))}
    </>
  );
}
