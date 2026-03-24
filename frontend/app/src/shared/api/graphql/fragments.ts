export const nodeCoreFragment = {
  id: true,
  display_label: true,
  hfid: true,
  __typename: true,
} as const;

export const nodeMetadataFragment = {
  node_metadata: {
    created_at: true,
    created_by: nodeCoreFragment,
    updated_at: true,
    updated_by: nodeCoreFragment,
  },
} as const;
