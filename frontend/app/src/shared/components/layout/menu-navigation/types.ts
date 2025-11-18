import type { components } from "@/shared/api/rest/types.generated";

export type MenuItem = components["schemas"]["MenuItemList"];

export type MenuData = {
  sections: {
    object: MenuItem[];
    internal: MenuItem[];
  };
};
