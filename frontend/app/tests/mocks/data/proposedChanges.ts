export const proposedChangesDetails = {
  id: "ce7e8cd8-45bd-41fa-b6b9-02097eb69274",
  display_label: "test",
  __typename: "CoreProposedChange",
  _updated_at: "2023-08-23T11:48:28.896430+00:00",
  name: { value: "test", __typename: "TextAttribute" },
  source_branch: { value: "jfk1-update-edge-ips", __typename: "TextAttribute" },
  destination_branch: { value: "main", __typename: "TextAttribute" },
  state: { value: "open", __typename: "TextAttribute" },
  approved_by: { edges: [], __typename: "NestedPaginatedCoreAccount" },
  reviewers: { edges: [], __typename: "NestedPaginatedCoreAccount" },
  created_by: {
    node: {
      id: "9709d335-e407-49c1-9b74-a75e3976d100",
      display_label: "Admin",
      __typename: "CoreAccount",
    },
    __typename: "NestedEdgedCoreAccount",
  },
};
