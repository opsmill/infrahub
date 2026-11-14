import type { InstanceColor } from "@/shared/api/graphql/generated/types";

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
  // A favicon is rendered outside the page, so it cannot read the theme tokens.
  faviconColor: string;
  label: string;
}

// The order is the one the color picker lists the presets in.
const INSTANCE_COLOR_PRESETS: Record<InstanceColor, InstanceColorPreset> = {
  RED: { badgeVariant: "red", barClassName: "bg-danger", faviconColor: "#be123c", label: "Red" },
  AMBER: {
    badgeVariant: "warning",
    barClassName: "bg-warning-strong",
    faviconColor: "#f59e0b",
    label: "Amber",
  },
  GREEN: {
    badgeVariant: "green",
    barClassName: "bg-success",
    faviconColor: "#15803d",
    label: "Green",
  },
  BLUE: { badgeVariant: "blue", barClassName: "bg-info", faviconColor: "#0369a1", label: "Blue" },
  INDIGO: {
    badgeVariant: "indigo",
    barClassName: "bg-active",
    faviconColor: "#4338ca",
    label: "Indigo",
  },
  PURPLE: {
    badgeVariant: "purple",
    barClassName: "bg-purple-600 dark:bg-purple-400",
    faviconColor: "#9333ea",
    label: "Purple",
  },
  GRAY: {
    badgeVariant: "gray",
    barClassName: "bg-foreground-muted",
    faviconColor: "#57534e",
    label: "Gray",
  },
};

const UNSET_INSTANCE_BADGE_VARIANT: InstanceBadgeVariant = "gray";

export function isInstanceColor(value: unknown): value is InstanceColor {
  return typeof value === "string" && Object.hasOwn(INSTANCE_COLOR_PRESETS, value);
}

export const INSTANCE_COLORS: Array<InstanceColor> =
  Object.keys(INSTANCE_COLOR_PRESETS).filter(isInstanceColor);

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

export function instanceBarClassName(color: string | null): string | null {
  return isInstanceColor(color) ? INSTANCE_COLOR_PRESETS[color].barClassName : null;
}

export function instanceFaviconColor(color: string | null): string | null {
  return isInstanceColor(color) ? INSTANCE_COLOR_PRESETS[color].faviconColor : null;
}
