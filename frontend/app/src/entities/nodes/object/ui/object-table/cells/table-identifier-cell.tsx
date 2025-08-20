import { useAuth } from "@/entities/authentication/ui/useAuth";
import { StickyLeftCell } from "@/entities/nodes/object/ui/object-table/cells/style";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { Checkbox } from "@/shared/components/aria/checkbox";
import { LinkButton } from "@/shared/components/buttons/button-primitive";

export interface TableIdentifierCellProps {
  objectKind: string;
  objectId: string;
  label: React.ReactNode;
  isSelected?: boolean;
  onSelectionChange?: (isSelected: boolean) => void;
}

export function TableIdentifierCell({
  objectKind,
  objectId,
  label,
  isSelected,
  onSelectionChange,
}: TableIdentifierCellProps) {
  const { isAuthenticated } = useAuth();
  return (
    <StickyLeftCell data-testid="identifier-cell">
      {isAuthenticated && (
        <Checkbox
          isSelected={isSelected}
          onChange={onSelectionChange}
          data-testid="identifier-checkbox-cell"
        />
      )}

      <LinkButton
        variant="ghost"
        size="sm"
        to={getObjectDetailsUrl(objectKind, objectId)}
        className="truncate px-2.5 rounded-full text-custom-blue-700 hover:underline hover:bg-custom-blue-700/10"
      >
        {label}
      </LinkButton>
    </StickyLeftCell>
  );
}
