export type GroupDataFromAPI = {
  id: string;
  display_label: string;
  description: { value: string } | null;
  members: {
    count: number;
  };
  group_type: { value: string } | null;
  __typename: string;
};
