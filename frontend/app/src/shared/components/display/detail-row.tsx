import { Icon } from "@iconify-icon/react";
import type React from "react";

import { classNames } from "@/shared/utils/common";

export interface DetailRowProps {
  /** Optional leading icon: an mdi icon name (string) or a ready-made node. */
  icon?: string | React.ReactNode;
  /** The field label, shown in the term (`<dt>`) cell. */
  label: React.ReactNode;
  /** When provided, the label gets this id so a control can `aria-labelledby` it. */
  labelId?: string;
  /** The value or control, shown in the definition (`<dd>`) cell. */
  children: React.ReactNode;
  className?: string;
}

/**
 * Generic object-details-style row: a fixed-width labelled term beside its value.
 * Mirrors the visual of the object-details data row (icon + muted label, value
 * cell) but carries no schema, dialog, or query coupling, so it is reusable for
 * any label/value pair (e.g. the preferences form).
 */
export function DetailRow({ icon, label, labelId, children, className }: DetailRowProps) {
  return (
    <dl className={classNames("grid grid-cols-[200px_auto] gap-4 px-3 py-2 text-sm", className)}>
      <dt className="flex items-center gap-1.5 font-medium text-gray-500">
        {typeof icon === "string" ? <Icon icon={icon} /> : icon}
        <span id={labelId}>{label}</span>
      </dt>
      <dd className="flex flex-col gap-1">{children}</dd>
    </dl>
  );
}
