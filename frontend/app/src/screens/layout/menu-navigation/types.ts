import { components } from "@/infraops";

export type MenuItem = components["schemas"]["MenuItemList"];

export type MenuData = {
  sections: {
    object: MenuItem[];
    internal: MenuItem[];
  };
};
