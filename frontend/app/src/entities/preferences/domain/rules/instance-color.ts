import type { InstanceColor } from "@/entities/preferences/domain/model/instance-identity";

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

const INSTANCE_COLOR_PRESETS: Record<InstanceColor, InstanceColorPreset> = {
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
};

const UNSET_INSTANCE_BADGE_VARIANT: InstanceBadgeVariant = "gray";

export const INSTANCE_COLOR_LABELS: Record<InstanceColor, string> = {
  RED: INSTANCE_COLOR_PRESETS.RED.label,
  AMBER: INSTANCE_COLOR_PRESETS.AMBER.label,
  GREEN: INSTANCE_COLOR_PRESETS.GREEN.label,
  BLUE: INSTANCE_COLOR_PRESETS.BLUE.label,
  INDIGO: INSTANCE_COLOR_PRESETS.INDIGO.label,
  PURPLE: INSTANCE_COLOR_PRESETS.PURPLE.label,
  GRAY: INSTANCE_COLOR_PRESETS.GRAY.label,
};

export function instanceBadgeVariant(
  color: InstanceColor | null | undefined
): InstanceBadgeVariant {
  return color ? INSTANCE_COLOR_PRESETS[color].badgeVariant : UNSET_INSTANCE_BADGE_VARIANT;
}

export function instanceBarClassName(color: InstanceColor): string {
  return INSTANCE_COLOR_PRESETS[color].barClassName;
}
