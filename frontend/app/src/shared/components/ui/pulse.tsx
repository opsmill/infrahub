import type React from "react";

import { classNames } from "@/shared/utils/common";

/**
 * What the pulse is reporting. The colour carries meaning, so it is a prop rather than
 * something each call site paints over: `info` is "something is happening", `danger` is
 * "something is wrong". Two pulses of the same colour sitting next to each other in the
 * header would say the same thing while meaning opposite things.
 */
type PulseTone = "info" | "danger";

const TONE_CLASSES: Record<PulseTone, { ping: string; dot: string }> = {
  info: { ping: "bg-custom-blue-500", dot: "bg-custom-blue-700" },
  danger: { ping: "bg-red-500", dot: "bg-red-600" },
};

interface PulseProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: PulseTone;
}

export function Pulse({ className, tone = "info", ...props }: PulseProps) {
  const { ping, dot } = TONE_CLASSES[tone];

  return (
    // Decorative: the state it accompanies is already named in the control's accessible
    // label, so announcing the dot as well would only repeat it.
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
