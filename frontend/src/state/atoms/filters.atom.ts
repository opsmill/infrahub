import { atom } from "jotai";

export interface iComboBoxFilter {
  name: string;
  value: string;
  display_label: string;
}

export const comboxBoxFilterState = atom<iComboBoxFilter[]>([]);
