export const GROUP_GENERIC = "CoreGroup";
export const GROUP_MEMBERS_RELATIONSHIP = "members";

export type GroupData = {
  id: string;
  display_label: string;
  description: { value: string } | null;
  members: {
    count: number;
  };
  group_type: { value: string } | null;
  __typename: string;
};
