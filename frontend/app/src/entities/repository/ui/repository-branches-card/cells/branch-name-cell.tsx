import { LinkButton, Tooltip } from "@infrahub/ui";

import { TableCell } from "@/shared/components/table/table-cell";

import { BranchDefaultBadge } from "@/entities/branches/ui/branch-list-item/branch-default-badge";
import { getBranchDetailsUrl } from "@/entities/branches/ui/routing/branch-urls";

interface BranchNameCellProps {
  name: string;
  isDefault: boolean;
  role?: React.AriaRole;
}

export function BranchNameCell({ name, isDefault, role }: BranchNameCellProps) {
  return (
    <TableCell className="font-medium" role={role}>
      <Tooltip message={name}>
        <LinkButton
          variant="ghost"
          size="sm"
          href={getBranchDetailsUrl(name)}
          className="min-w-0 shrink rounded-full px-2.5 text-accent data-hovered:bg-accent/10 data-hovered:underline"
        >
          {/* The ellipsis has to sit on a child: `text-overflow` does nothing on
              the button's own flex box. */}
          <span className="truncate">{name}</span>
        </LinkButton>
      </Tooltip>

      {isDefault && <BranchDefaultBadge aria-label="Default branch" />}
    </TableCell>
  );
}
