import { makeVar } from "@apollo/client";

export interface iComboBoxFilter {
  name: string;
  value: string;
  display_label: string;
}

export const comboxBoxFilterVar = makeVar([]);
