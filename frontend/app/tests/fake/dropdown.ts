import type { Dropdown } from "@/shared/api/graphql/generated/types";

export type DropdownSelection = Pick<Dropdown, "value" | "label" | "color" | "description">;

export const generateDropdown = (overrides?: Partial<DropdownSelection>): DropdownSelection => ({
  value: "in-sync",
  label: "In sync",
  color: "#7fbf7f",
  description: "The imported commit matches the remote",
  ...overrides,
});

export const generateInternalStatusDropdown = (
  overrides?: Partial<DropdownSelection>
): DropdownSelection => ({
  value: "active",
  label: "Active",
  color: "#4b9f4b",
  description: "The repository is active on this branch",
  ...overrides,
});

// No schema declares this triple, so a label or colour it renders with can only have come from the
// payload — which is what makes it worth asserting.
export const generateInventedDropdown = (
  overrides?: Partial<DropdownSelection>
): DropdownSelection => ({
  value: "quarantined",
  label: "Quarantined",
  color: "#4c1d95",
  description: "Invented status",
  ...overrides,
});
