import type React from "react";

import { classNames } from "@/shared/utils/common";

/** What the pulse reports: `info` for activity, `danger` for a failure. */
type PulseTone = "info" | "danger";

const TONE_CLASSES: Record<PulseTone, { ping: string; dot: string }> = {
  info: { ping: "bg-custom-blue-500", dot: "bg-custom-blue-700" },
  danger: { ping: "bg-danger", dot: "bg-danger" },
};

interface PulseProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: PulseTone;
}

export function Pulse({ className, tone = "info", ...props }: PulseProps) {
  const { ping, dot } = TONE_CLASSES[tone];

  return (
    <span aria-hidden className={classNames("absolute flex h-2 w-2", className)} {...props}>
      <span
        className={classNames(
          "absolute inline-flex h-full w-full animate-ping rounded-full opacity-75",
          ping
        )}
      ></span>
      <span className={classNames("relative inline-flex h-2 w-2 rounded-full", dot)}></span>
    </span>
  );
}
