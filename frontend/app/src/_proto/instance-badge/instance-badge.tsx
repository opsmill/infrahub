// PROTOTYPE design-jam instance-badge
import { Tooltip } from "@infrahub/ui";

import { Badge } from "@/shared/components/ui/badge";
import { classNames } from "@/shared/utils/common";

import { barHeightClass, PRESET_STYLE, type Preset } from "./fixtures";

type InstanceBadgeProps = {
  label: string;
  color: Preset | null;
  className?: string;
};

const TRUNCATION = "inline-block max-w-48 shrink-0 truncate align-middle";

/** Tinted badge on the existing Badge variants; gray when the administrator set no color. */
export function InstanceBadge({ label, color, className }: InstanceBadgeProps) {
  if (!label) return null;

  const style = PRESET_STYLE[color ?? "gray"];

  return (
    <Tooltip message={label} nonInteractiveTrigger>
      <Badge
        variant={style.badge ?? "gray"}
        className={classNames(TRUNCATION, style.badgeClass, className)}
      >
        {label}
      </Badge>
    </Tooltip>
  );
}

/** Filled badge on the strong token of each preset. */
export function SolidInstanceBadge({ label, color, className }: InstanceBadgeProps) {
  if (!label) return null;

  const style = PRESET_STYLE[color ?? "gray"];

  return (
    <Tooltip message={label} nonInteractiveTrigger>
      <span
        className={classNames(
          "rounded-md border border-transparent px-1.5 py-0.5 font-semibold text-xs",
          TRUNCATION,
          style.solid,
          className
        )}
      >
        {label}
      </span>
    </Tooltip>
  );
}

type InstanceBarProps = {
  color: Preset | null;
  height: number;
};

/** Thin full-width line in the instance color; nothing when no color is set. */
export function InstanceBar({ color, height }: InstanceBarProps) {
  if (!color) return null;

  return (
    <div
      aria-hidden
      className={classNames("w-full shrink-0", barHeightClass(height), PRESET_STYLE[color].bar)}
    />
  );
}
