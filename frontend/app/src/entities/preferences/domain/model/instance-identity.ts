import type { Config } from "@/entities/config/domain/model/config";

export type InstanceIdentity = Config["instance"];

export type InstanceColor = NonNullable<InstanceIdentity["color"]>;

export const INSTANCE_COLORS: ReadonlyArray<InstanceColor> = [
  "RED",
  "AMBER",
  "GREEN",
  "BLUE",
  "INDIGO",
  "PURPLE",
  "GRAY",
];

export const INSTANCE_LABEL_MAX_LENGTH = 32;

export const DOCUMENT_TITLE_SEPARATOR = " · ";
