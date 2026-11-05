import type { Config } from "@/entities/config/domain/model/config";

type InstanceIdentity = Config["instance"];

export type InstanceColor = NonNullable<InstanceIdentity["color"]>;

// The order is the one the color picker lists the presets in.
export const INSTANCE_COLORS = [
  "RED",
  "AMBER",
  "GREEN",
  "BLUE",
  "INDIGO",
  "PURPLE",
  "GRAY",
] as const satisfies ReadonlyArray<InstanceColor>;

export function isInstanceColor(value: unknown): value is InstanceColor {
  return typeof value === "string" && INSTANCE_COLORS.some((color) => color === value);
}

export const INSTANCE_LABEL_MAX_LENGTH = 32;
