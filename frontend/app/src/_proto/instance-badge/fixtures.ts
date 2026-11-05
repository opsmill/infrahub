// PROTOTYPE design-jam instance-badge
import type { KnobValue } from "./design-history-panel";

export const BRANCH_NAME = "feature/ipam-prefix-reallocation-2026-q4";

export const BREADCRUMB = ["Objects", "IPAM", "Prefixes", "10.240.128.0/17", "Relationships"];

export const MENU_ITEMS: { label: string; icon: string }[] = [
  { label: "Objects", icon: "mdi:cube-outline" },
  { label: "IPAM", icon: "mdi:ip-network-outline" },
  { label: "Proposed changes", icon: "mdi:source-pull" },
  { label: "Branches", icon: "mdi:source-branch" },
  { label: "Repositories", icon: "mdi:git" },
  { label: "Tasks", icon: "mdi:progress-check" },
  { label: "Schema", icon: "mdi:file-tree-outline" },
  { label: "Admin", icon: "mdi:shield-account-outline" },
];

export const CHILD_PREFIXES: { prefix: string; description: string; status: string }[] = [
  { prefix: "10.240.128.0/20", description: "zrh-west-2 core leaf fabric", status: "active" },
  { prefix: "10.240.144.0/20", description: "zrh-west-2 storage front-end", status: "active" },
  { prefix: "10.240.160.0/21", description: "zrh-west-2 management", status: "reserved" },
  { prefix: "10.240.168.0/21", description: "zrh-west-2 out-of-band", status: "active" },
  {
    prefix: "10.240.176.0/20",
    description: "zrh-west-2 tenant overlay pool",
    status: "deprecated",
  },
  { prefix: "10.240.192.0/18", description: "reallocation target, 2026 Q4", status: "reserved" },
];

export const LABEL_OPTIONS = ["none", "PROD", "us-east-1 PROD", "zurich-west-2 PRODUCTION-MAIN"];

export const PRESETS = ["red", "amber", "green", "blue", "indigo", "purple", "gray"] as const;
export type Preset = (typeof PRESETS)[number];
export const COLOR_OPTIONS = ["none", ...PRESETS];

export type BadgeVariant = "red" | "warning" | "green" | "blue" | "purple" | "gray";

export type PresetStyle = {
  /** Existing Badge variant, or null when the prototype styles the badge itself. */
  badge: BadgeVariant | null;
  /** Tint classes applied on top of the Badge when `badge` is null. */
  badgeClass?: string;
  bar: string;
  /** Filled badge: the strong token as background, text picked for that fill in each theme. */
  solid: string;
};

export const PRESET_STYLE: Record<Preset, PresetStyle> = {
  red: {
    badge: "red",
    bar: "bg-danger",
    solid: "bg-danger text-white dark:text-rose-950",
  },
  amber: {
    badge: "warning",
    bar: "bg-warning-strong",
    solid: "bg-warning-strong text-amber-950",
  },
  green: {
    badge: "green",
    bar: "bg-success",
    solid: "bg-success text-white dark:text-green-950",
  },
  blue: {
    badge: "blue",
    bar: "bg-info",
    solid: "bg-info text-white dark:text-sky-950",
  },
  indigo: {
    badge: null,
    badgeClass: "bg-active-surface text-active",
    bar: "bg-active",
    solid: "bg-active text-white dark:text-indigo-950",
  },
  purple: {
    badge: "purple",
    bar: "bg-purple-600 dark:bg-purple-400",
    solid: "bg-purple-600 text-white dark:bg-purple-400 dark:text-purple-950",
  },
  gray: {
    badge: "gray",
    bar: "bg-foreground-muted",
    solid: "bg-foreground-muted text-background",
  },
};

export const BAR_HEIGHT_MIN = 1;
export const BAR_HEIGHT_MAX = 6;
export const BAR_HEIGHT_DEFAULT = 3;

const BAR_HEIGHT_CLASS: Record<number, string> = {
  1: "h-px",
  2: "h-0.5",
  3: "h-0.75",
  4: "h-1",
  5: "h-1.25",
  6: "h-1.5",
};

export const barHeightClass = (px: number): string =>
  BAR_HEIGHT_CLASS[px] ?? BAR_HEIGHT_CLASS[BAR_HEIGHT_DEFAULT] ?? "h-0.75";

export const STRIP_HEIGHT_MIN = 16;
export const STRIP_HEIGHT_MAX = 28;
export const STRIP_HEIGHT_STEP = 4;
export const STRIP_HEIGHT_DEFAULT = 20;

const STRIP_HEIGHT_CLASS: Record<number, string> = {
  16: "h-4",
  20: "h-5",
  24: "h-6",
  28: "h-7",
};

export const stripHeightClass = (px: number): string =>
  STRIP_HEIGHT_CLASS[px] ?? STRIP_HEIGHT_CLASS[STRIP_HEIGHT_DEFAULT] ?? "h-5";

export type SharedKnobs = {
  label: string;
  color: Preset | null;
  screen: "app" | "login";
  collapsed: boolean;
  dark: boolean;
  barHeight: number;
};

const text = (value: KnobValue | undefined): string => (typeof value === "string" ? value : "");

const number = (value: KnobValue | undefined, fallback: number): number =>
  typeof value === "number" && Number.isFinite(value) ? value : fallback;

export const readSharedKnobs = (knobs: Record<string, KnobValue>): SharedKnobs => {
  const label = text(knobs.label);
  const color = text(knobs.color);
  return {
    label: label === "none" ? "" : label,
    color: PRESETS.find((preset) => preset === color) ?? null,
    screen: text(knobs.screen) === "login" ? "login" : "app",
    collapsed: text(knobs.sidebar) === "collapsed",
    dark: text(knobs.theme) === "dark",
    barHeight: Math.min(
      BAR_HEIGHT_MAX,
      Math.max(BAR_HEIGHT_MIN, Math.round(number(knobs.barHeight, BAR_HEIGHT_DEFAULT)))
    ),
  };
};

export const readStripHeight = (knobs: Record<string, KnobValue>): number => {
  const value = Math.round(number(knobs.stripHeight, STRIP_HEIGHT_DEFAULT) / STRIP_HEIGHT_STEP);
  return Math.min(STRIP_HEIGHT_MAX, Math.max(STRIP_HEIGHT_MIN, value * STRIP_HEIGHT_STEP));
};
