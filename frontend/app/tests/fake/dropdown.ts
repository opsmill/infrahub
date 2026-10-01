import type { Dropdown } from "@/shared/api/graphql/generated/types";

export type DropdownSelection = Pick<Dropdown, "value" | "label" | "color" | "description">;

export const generateDropdown = (overrides?: Partial<DropdownSelection>): DropdownSelection => ({
  value: "in-sync",
  label: "In sync",
  color: "#7fbf7f",
  description: "The imported commit matches the remote",
  ...overrides,
});
