import { Checkbox, LinkButton, Tooltip } from "@infrahub/ui";
import type { PressEvent } from "react-aria-components";

import { Col, Row } from "@/shared/components/container";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import { BranchDefaultBadge } from "@/entities/branches/ui/branch-list-item/branch-default-badge";
import { BranchGitSyncBadge } from "@/entities/branches/ui/branch-list-item/branch-git-sync-badge";
import { BranchSchemaChangesBadge } from "@/entities/branches/ui/branch-list-item/branch-schema-changes-badge";
import { getBranchDetailsUrl } from "@/entities/branches/ui/routing/branch-urls";
import { StickyLeftCell } from "@/entities/nodes/object/ui/object-table/cells/style";

interface BranchNameCellProps {
  branch: BranchListItem;
  isSelected?: boolean;
  onClickCheckbox?: (e: PressEvent) => void;
}

export function BranchNameCell({ branch, isSelected, onClickCheckbox }: BranchNameCellProps) {
  const { isAuthenticated } = useAuth();

  return (
    <StickyLeftCell
      className="h-auto min-h-14 items-start gap-1.5"
      data-testid="branch-identifier-cell"
    >
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
<<<<<<< HEAD
          <LinkButton
            variant="ghost"
            size="sm"
            href={getBranchDetailsUrl(branch.name)}
            className="truncate rounded-full px-2.5 text-accent data-hovered:bg-accent/10 data-hovered:underline"
          >
            {branch.name}
          </LinkButton>
=======
          <Tooltip message={branch.name}>
            <LinkButton
              variant="ghost"
              size="sm"
              href={getBranchDetailsUrl(branch.name)}
              className="min-w-0 shrink rounded-full px-2.5 text-custom-blue-700 data-hovered:bg-custom-blue-700/10 data-hovered:underline"
            >
              {/* The ellipsis has to sit on a child: `text-overflow` does nothing on
                  the button's own flex box. */}
              <span className="truncate">{branch.name}</span>
            </LinkButton>
          </Tooltip>
>>>>>>> origin/stable

          <Row className="gap-1">
            {branch.is_default && <BranchDefaultBadge />}

            {branch.schema_differs_from_default_branch && <BranchSchemaChangesBadge />}

            {branch.sync_with_git && <BranchGitSyncBadge />}
          </Row>
        </Row>

        {branch.description && (
          <span className="truncate pl-2.5 text-foreground-muted text-xs">
            {branch.description}
          </span>
        )}
      </Col>
    </StickyLeftCell>
  );
}
