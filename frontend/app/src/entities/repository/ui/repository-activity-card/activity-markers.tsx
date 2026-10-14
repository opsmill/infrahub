import type React from "react";

import { Pulse } from "@/shared/components/ui/pulse";
import { classNames } from "@/shared/utils/common";

// Every row starts with an 8px marker column, so the text of every row lines up.
const MARKER_COLUMN = "flex w-2 shrink-0 justify-center";

export function LiveMarker() {
  return (
    <span aria-hidden className={MARKER_COLUMN}>
      <span className="relative size-2">
        <Pulse />
      </span>
    </span>
  );
}

export function DotMarker({ tone }: { tone: "neutral" | "danger" }) {
  return (
    <span aria-hidden className={MARKER_COLUMN}>
      <span
        className={classNames(
          "size-2 rounded-full",
          tone === "danger" ? "bg-danger" : "bg-foreground-muted/30"
        )}
      />
    </span>
  );
}

/** Centres an icon wider than the column on it, so the icon sits where the dots sit. */
export function IconMarker({ children }: { children: React.ReactNode }) {
  return (
    <span aria-hidden className={classNames(MARKER_COLUMN, "text-foreground-muted")}>
      {children}
    </span>
  );
}
