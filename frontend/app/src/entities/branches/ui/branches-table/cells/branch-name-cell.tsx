import type { PressEvent } from "react-aria-components";

import { constructPath } from "@/shared/api/rest/fetch";
import { Checkbox } from "@/shared/components/aria/checkbox";
import { LinkButton } from "@/shared/components/buttons/button-primitive";
import { Col, Row } from "@/shared/components/container";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import type { BranchListItem } from "@/entities/branches/domain/branch.mappers";
import { BranchDefaultBadge } from "@/entities/branches/ui/branch-list-item/branch-default-badge";
import { BranchGitSyncBadge } from "@/entities/branches/ui/branch-list-item/branch-git-sync-badge";
import { BranchSchemaChangesBadge } from "@/entities/branches/ui/branch-list-item/branch-schema-changes-badge";
import { BranchStatusBadge } from "@/entities/branches/ui/branch-list-item/branch-status-badge";
import { StickyLeftCell } from "@/entities/nodes/object/ui/object-table/cells/style";

interface BranchNameCellProps {
  branch: BranchListItem;
  isSelected?: boolean;
  onClickCheckbox?: (e: PressEvent) => void;
}

export function BranchNameCell({ branch, isSelected, onClickCheckbox }: BranchNameCellProps) {
  const { isAuthenticated } = useAuth();

  return (
    <StickyLeftCell className="h-auto min-h-14 items-start gap-1.5" data-testid="branch-identifier-cell">
      {isAuthenticated && (
        <Checkbox
          isSelected={isSelected}
          onPress={onClickCheckbox}
          data-testid="branch-checkbox-cell"
          className="mt-2"
        />
      )}

      <Col className="gap-0.5 overflow-hidden">
        <Row className="gap-1">
          <LinkButton
            variant="ghost"
            size="sm"
            to={constructPath(`/branches/${branch.name}`)}
            className="truncate rounded-full px-2.5 text-custom-blue-700 hover:bg-custom-blue-700/10 hover:underline"
          >
            {branch.name}
          </LinkButton>

          <Row className="gap-1">
            {branch.is_default ? (
              <BranchDefaultBadge />
            ) : (
              <BranchStatusBadge status={branch.status} />
            )}

            {branch.has_schema_changes && <BranchSchemaChangesBadge />}

            {branch.sync_with_git && <BranchGitSyncBadge />}
          </Row>
        </Row>

        {branch.description && (
          <span className="truncate pl-2.5 text-gray-600 text-xs">{branch.description}</span>
        )}
      </Col>
    </StickyLeftCell>
  );
}
