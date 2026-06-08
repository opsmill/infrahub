import type { NodeAttribute, NodeCore, NodeRelationshipMany } from "@/entities/nodes/types";

export interface ProposedChangeDetail extends NodeCore {
  __typename: "CoreProposedChange";
  name: NodeAttribute<string>;
  description: NodeAttribute<string> & { updated_at: string };
  source_branch: NodeAttribute<string>;
  destination_branch: NodeAttribute<string>;
  state: NodeAttribute<string>;
  is_draft: NodeAttribute<boolean>;
  approved_by: NodeRelationshipMany;
  rejected_by: NodeRelationshipMany;
  reviewers: NodeRelationshipMany;
  comments: { count: number };
}
