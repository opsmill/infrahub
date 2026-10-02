import type { Dropdown } from "@/shared/api/graphql/generated/types";

export type DropdownSelection = Pick<Dropdown, "value" | "label" | "color" | "description">;

export const generateDropdown = (overrides?: Partial<DropdownSelection>): DropdownSelection => ({
  value: "in-sync",
  label: "In Sync",
  color: "#60a5fa",
  description: "The repository is syncing correctly",
  ...overrides,
});
