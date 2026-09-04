import type { MenuItem } from "../../src/entities/navigation/domain/model/menu";

export const generateMenuItem = (override: Partial<MenuItem> = {}): MenuItem => {
  const label = override.label ?? "Menu item";

  return {
    id: `menu-${label}`,
    namespace: "Builtin",
    name: label.replace(/\s/g, ""),
    description: "",
    protected: false,
    label,
    path: `/objects/${label.replace(/\s/g, "")}`,
    icon: "mdi:cube-outline",
    kind: "",
    order_weight: 5000,
    section: "object",
    identifier: `menu-${label}`,
    ...override,
  };
};

/** `count` sibling menu items, labelled `<prefix> 1`..`<prefix> N`. */
export const generateMenuItems = (
  count: number,
  prefix: string,
  override: Partial<MenuItem> = {}
): MenuItem[] =>
  Array.from({ length: count }, (_, index) =>
    generateMenuItem({ label: `${prefix} ${index + 1}`, ...override })
  );
