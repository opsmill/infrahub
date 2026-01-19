import { Icon } from "@iconify-icon/react";
import { Link } from "react-router";
import { PROPOSED_CHANGE_OBJECT } from "@/entities/proposed-changes/constants";
import { useGetProposedChanges } from "@/entities/proposed-changes/domain/get-proposed-changes.query";
import { useCoreSchema } from "@/entities/schema/ui/hooks/useCoreSchema";
import { getSchemaIcon } from "@/entities/schema/utils/get-schema-icon";
import { constructPath } from "@/shared/api/rest/fetch";
import { LinkButton } from "@/shared/components/buttons/button-primitive";
import { TableCell } from "@/shared/components/table/table-cell";
import { QSP } from "@/shared/config/qsp";

interface BranchProposedChangesCellProps {
	branchName: string;
}

export function BranchProposedChangesCell({
	branchName,
}: BranchProposedChangesCellProps) {
	// Use Core schema hook - guaranteed to exist for Core namespace objects
	const { schema } = useCoreSchema(PROPOSED_CHANGE_OBJECT);

	// Query proposed changes for this specific branch
	const { data: proposedChangesData } = useGetProposedChanges({
		schema,
		filters: [{ name: "source_branch__value", value: branchName }],
	});

	// Get all proposed changes from all pages
	const proposedChanges = proposedChangesData?.pages?.flat() ?? [];
	const firstPC = proposedChanges[0];

	// Show empty state if no proposed changes
	if (!firstPC) {
		return (
			<TableCell className="h-auto min-h-14">
				<span className="text-gray-400">-</span>
			</TableCell>
		);
	}

	const remainingCount = proposedChanges.length - 1;

	// URL for first proposed change detail
	const detailUrl = constructPath(`/proposed-changes/${firstPC.id}`);

	// URL for filtered list (if more than one)
	const listUrl = constructPath("/proposed-changes", [
		{
			name: QSP.FILTER,
			value: JSON.stringify([
				{ name: "source_branch__value", value: branchName },
			]),
		},
	]);

	return (
		<TableCell className="h-auto min-h-14">
			<div className="flex items-center gap-2">
				<LinkButton
					variant="outline"
					size="sm"
					to={detailUrl}
					className="truncate rounded-full pr-2.5 hover:border-custom-blue-700 hover:underline"
				>
					<Icon
						icon={getSchemaIcon(schema)}
						className="mr-1 text-custom-blue-800"
					/>
					{firstPC.node.name.value}
				</LinkButton>

				{remainingCount > 0 && (
					<Link
						to={listUrl}
						className="whitespace-nowrap text-gray-500 text-sm hover:underline"
					>
						+{remainingCount} more
					</Link>
				)}
			</div>
		</TableCell>
	);
}
