/** Each choice is a field key (for example "serial_number" or "device_type.manufacturer"). */
export interface LabelChoices {
  rack: string;
  item: string;
  subtitle: string;
}

export const MAPPED_LABEL = "__mapped__";
export const HIDDEN_LABEL = "__hidden__";

export interface LabelOption {
  key: string;
  label: string;
  count: number;
}
