export interface PreferenceValues {
  dateFormat: string | null;
  timezone: string | null;
}

export interface PreferenceNode extends PreferenceValues {
  id: string;
}
