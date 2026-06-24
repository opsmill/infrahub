import type { NodeCore } from "@/entities/nodes/types";

export type RelationshipNode = {
  id: string;
  display_label: string;
  __typename: string;
  /** Present only for IP address pool peers; used as the prefix-length placeholder. */
  default_prefix_length?: { value?: number | null } | null;
};

export type RelationshipProperties = {
  is_protected: boolean;
  updated_at: Date;
  source: NodeCore | null;
  owner: NodeCore | null;
};
