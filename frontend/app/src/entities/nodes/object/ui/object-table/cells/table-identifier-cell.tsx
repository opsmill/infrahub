import type { PressEvent } from "react-aria-components";

import { Checkbox } from "@/shared/components/aria/checkbox";
import { LinkButton } from "@/shared/components/ui/button";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { StickyLeftCell } from "@/entities/nodes/object/ui/object-table/cells/style";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";

export interface TableIdentifierCellProps {
  objectKind: string;
  objectId: string;
  label: React.ReactNode;
  isSelected?: boolean;
  onClickCheckbox?: (e: PressEvent) => void;
}

export function TableIdentifierCell({
  objectKind,
  objectId,
  label,
  isSelected,
  onClickCheckbox,
}: TableIdentifierCellProps) {
  const { isAuthenticated } = useAuth();
  return (
    <StickyLeftCell data-testid="identifier-cell">
      {isAuthenticated && (
        <Checkbox
          isSelected={isSelected}
          onPress={onClickCheckbox}
          data-testid="identifier-checkbox-cell"
        />
      )}

      <LinkButton
        variant="ghost"
        size="sm"
        to={getObjectDetailsUrl(objectKind, objectId)}
        className="-mx-1 truncate rounded-xl px-2 text-custom-blue-700 hover:underline"
      >
        {label}
      </LinkButton>
    </StickyLeftCell>
  );
}
