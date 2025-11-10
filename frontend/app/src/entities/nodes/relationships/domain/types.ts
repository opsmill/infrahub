import type { NodeCore } from "@/entities/nodes/types";

export type RelationshipNode = {
  id: string;
  display_label: string;
  __typename: string;
};

export type RelationshipProperties = {
  is_visible: boolean;
  is_protected: boolean;
  updated_at: Date;
  source: NodeCore | null;
  owner: NodeCore | null;
};
