import { atom } from "jotai";
import { components } from "../../infraops";
import { MenuItem } from "../../screens/layout/sidebar/desktop-menu";

export type iNodeSchema = components["schemas"]["APINodeSchema"];
export const schemaState = atom<iNodeSchema[]>([]);

export type iGenericSchema = components["schemas"]["APIGenericSchema"];
export const genericsState = atom<iGenericSchema[]>([]);

export type IModelSchema = iGenericSchema | iNodeSchema;

export type iNamespace = {
  name: string;
  user_editable: boolean;
};
export const namespacesState = atom<iNamespace[]>([]);

export const currentSchemaHashAtom = atom<string | null>(null);

export const menuAtom = atom<MenuItem[]>([]);

const flattenMenuItems = (menuItems: MenuItem[]): MenuItem[] => {
  return menuItems.reduce<MenuItem[]>((acc, menuItem) => {
    if (menuItem.children.length === 0) {
      return [...acc, menuItem];
    }

    return [...acc, ...flattenMenuItems(menuItem.children)];
  }, []);
};

export const menuFlatAtom = atom((get) => flattenMenuItems(get(menuAtom)));
