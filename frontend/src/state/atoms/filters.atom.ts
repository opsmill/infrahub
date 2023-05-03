import { atom } from "jotai";

// Need to save the data type of the fiter value. Could be string | number | boolean
export interface iComboBoxFilter {
  name: string;
  value: string;
  display_label: string;
}

export const comboxBoxFilterState = atom<iComboBoxFilter[]>([]);
