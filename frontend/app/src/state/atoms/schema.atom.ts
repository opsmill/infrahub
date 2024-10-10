import { components } from "@/infraops";
import { MenuData, MenuItem } from "@/screens/layout/menu-navigation/types";
import { atom } from "jotai";

export type iNodeSchema = components["schemas"]["APINodeSchema"];
export const schemaState = atom<iNodeSchema[]>([]);

export type iGenericSchema = components["schemas"]["APIGenericSchema"];
export const genericsState = atom<iGenericSchema[]>([]);

export type IProfileSchema = components["schemas"]["APIProfileSchema"];
export const profilesAtom = atom<IProfileSchema[]>([]);

export type IModelSchema = iGenericSchema | iNodeSchema;

export type iNamespace = {
  name: string;
  user_editable: boolean;
};
export const namespacesState = atom<iNamespace[]>([]);

export const currentSchemaHashAtom = atom<string | null>(null);

export const menuAtom = atom<MenuData>();

export const menuFlatAtom = atom((get) => {
  const menuData = get(menuAtom);
  if (!menuData) return [];

  const menuItems: MenuItem[] = [];

  const flattenMenuItems = (menuItem: MenuItem) => {
    if (menuItem.path !== "") menuItems.push(menuItem);

    if (menuItem.children && menuItem.children.length > 0) {
      menuItem.children.forEach(flattenMenuItems);
    }
  };

  menuData.sections.object.forEach(flattenMenuItems);
  menuData.sections.internal.forEach(flattenMenuItems);

  return menuItems;
});
