import type React from "react";

import { Icon } from "@/shared/components/display/icon";
import { classNames } from "@/shared/utils/common";

export interface DetailRowProps {
  /** An mdi icon name (string) or a ready-made node. */
  icon?: string | React.ReactNode;
  label: React.ReactNode;
  /** Set so a control can reference the label via `aria-labelledby`. */
  labelId?: string;
  children: React.ReactNode;
  className?: string;
}

// Object-details-style row (icon + muted term, value cell) with no schema/query coupling.
export function DetailRow({ icon, label, labelId, children, className }: DetailRowProps) {
  return (
    <dl className={classNames("grid grid-cols-[200px_auto] gap-4 px-3 py-2 text-sm", className)}>
      <dt className="flex items-center gap-1.5 font-medium text-foreground-muted">
        {typeof icon === "string" ? <Icon icon={icon} /> : icon}
        <span id={labelId}>{label}</span>
      </dt>
      <dd className="flex flex-col gap-1 text-foreground">{children}</dd>
    </dl>
  );
}
