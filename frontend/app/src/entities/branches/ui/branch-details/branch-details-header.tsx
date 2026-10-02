import { CopyToClipboardButton } from "@/shared/components/buttons/copy-to-clipboard-button";

import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import { BranchDefaultBadge } from "@/entities/branches/ui/branch-list-item/branch-default-badge";
import { BranchStatusBadge } from "@/entities/branches/ui/branch-list-item/branch-status-badge";
import { branchesQueryKeys } from "@/entities/branches/ui/queries/branch.query-keys";
import { NodeMetadataPopover } from "@/entities/nodes/object/ui/metadata/node-metadata-popover";
import { HeaderContainer } from "@/entities/nodes/object/ui/object-details/object-details-header";
import { RefreshButton } from "@/entities/nodes/object/ui/object-details/refresh-button";
import { repositoryQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";
import { tasksQueryKeys } from "@/entities/tasks/ui/queries/tasks.query-keys";

// `all` rather than `details`: the header itself reads the all-branches query.
const REFRESHED_QUERY_KEYS = [branchesQueryKeys.all, repositoryQueryKeys.all, tasksQueryKeys.all];

interface BranchDetailsHeaderProps {
  branch: BranchListItem;
}

export function BranchDetailsHeader({ branch }: BranchDetailsHeaderProps) {
  return (
    <header>
      <HeaderContainer data-testid="branch-details-header">
        <h1 className="truncate font-bold text-xl" title={branch.name}>
          {branch.name}
        </h1>
        <CopyToClipboardButton data={branch.name} aria-label="Copy branch name" />
        <NodeMetadataPopover objectKind="InfrahubBranch" objectId={branch.id} />
        {branch.is_default ? (
          <BranchDefaultBadge className="text-sm" />
        ) : (
          <BranchStatusBadge status={branch.status} className="text-sm" />
        )}
        <RefreshButton className="ml-auto" queryKeys={REFRESHED_QUERY_KEYS} />
      </HeaderContainer>
      {branch.description && (
        <p className="-mt-1 max-w-prose text-pretty px-3 pb-1 text-sm">{branch.description}</p>
      )}
    </header>
  );
}
