import type { NodeCore } from "@/entities/nodes/types";
import type {
	Branch,
	InfrahubBranch,
	InfrahubBranchType,
	InfrahubNodeMetadata,
} from "@/shared/api/graphql/generated/graphql";
import { ACCOUNT_GENERIC_OBJECT } from "@/shared/config/constants";

export type InfrahubBranchResponse = {
	InfrahubBranch: InfrahubBranchType;
};

export interface BranchWithMetadata
	extends Omit<Branch, "created_at">,
		Omit<InfrahubNodeMetadata, "__typename" | "created_by" | "updated_by"> {
	created_by?: NodeCore | null;
}

interface MapInfrahubBranchNodeToBranchParams {
	node: InfrahubBranch;
	node_metadata: InfrahubNodeMetadata;
}

function mapCreatedByToNodeCore(
	createdBy: InfrahubNodeMetadata["created_by"],
): NodeCore | null {
	if (!createdBy?.id) return null;

	return {
		id: createdBy.id,
		display_label: createdBy.display_label,
		hfid: createdBy.hfid,
		__typename: ACCOUNT_GENERIC_OBJECT,
	};
}

export function mapInfrahubBranchNodeToBranch({
	node,
	node_metadata,
}: MapInfrahubBranchNodeToBranchParams): BranchWithMetadata {
	return {
		id: node.id,
		name: node.name.value,
		description: node.description?.value,
		origin_branch: node.origin_branch?.value,
		branched_from: node.branched_from?.value,
		status: node.status.value,
		sync_with_git: node.sync_with_git?.value,
		is_default: node.is_default?.value,
		has_schema_changes: node.has_schema_changes?.value,

		created_at: node_metadata.created_at,
		updated_at: node_metadata.updated_at,
		created_by: mapCreatedByToNodeCore(node_metadata.created_by),
	};
}
