import type { NodeCore } from "@/entities/nodes/types";

export type RelationshipNode = {
  id: string;
  display_label: string;
  __typename: string;
  default_prefix_length?: { value: number | null } | null;
};

export type RelationshipProperties = {
  is_protected: boolean;
  updated_at: Date;
  source: NodeCore | null;
  owner: NodeCore | null;
};
