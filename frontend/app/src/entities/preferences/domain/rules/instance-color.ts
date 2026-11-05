import {
  type InstanceColor,
  isInstanceColor,
} from "@/entities/preferences/domain/model/instance-identity";

export type InstanceBadgeVariant =
  | "red"
  | "warning"
  | "green"
  | "blue"
  | "indigo"
  | "purple"
  | "gray";

interface InstanceColorPreset {
  badgeVariant: InstanceBadgeVariant;
  barClassName: string;
  label: string;
}

const INSTANCE_COLOR_PRESETS = {
  RED: { badgeVariant: "red", barClassName: "bg-danger", label: "Red" },
  AMBER: { badgeVariant: "warning", barClassName: "bg-warning-strong", label: "Amber" },
  GREEN: { badgeVariant: "green", barClassName: "bg-success", label: "Green" },
  BLUE: { badgeVariant: "blue", barClassName: "bg-info", label: "Blue" },
  INDIGO: { badgeVariant: "indigo", barClassName: "bg-active", label: "Indigo" },
  PURPLE: {
    badgeVariant: "purple",
    barClassName: "bg-purple-600 dark:bg-purple-400",
    label: "Purple",
  },
  GRAY: { badgeVariant: "gray", barClassName: "bg-foreground-muted", label: "Gray" },
} satisfies Record<InstanceColor, InstanceColorPreset>;

const UNSET_INSTANCE_BADGE_VARIANT: InstanceBadgeVariant = "gray";

export function instanceColorLabel(color: InstanceColor): string {
  return INSTANCE_COLOR_PRESETS[color].label;
}

// A color the bundle does not know (the server was upgraded under a cached bundle) falls back
// to the unset rendering instead of breaking the page.
export function instanceBadgeVariant(color: string | null): InstanceBadgeVariant {
  return isInstanceColor(color)
    ? INSTANCE_COLOR_PRESETS[color].badgeVariant
    : UNSET_INSTANCE_BADGE_VARIANT;
}

export function instanceBarClassName(color: InstanceColor): string;
export function instanceBarClassName(color: string | null): string | null;
export function instanceBarClassName(color: string | null): string | null {
  return isInstanceColor(color) ? INSTANCE_COLOR_PRESETS[color].barClassName : null;
}
