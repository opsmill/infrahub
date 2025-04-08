import { useAuth } from "@/entities/authentication/ui/useAuth";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { Checkbox } from "@/shared/components/aria/checkbox";
import { LinkButton } from "@/shared/components/buttons/button-primitive";
import { TableCell } from "@/shared/components/table/table-cell";

export interface TableIdentifierCellProps {
  objectKind: string;
  objectId: string;
  label: string;
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
    <TableCell className="sticky left-0 bg-white" data-testid="identifier-cell">
      {isAuthenticated && <Checkbox isSelected={isSelected} onChange={onSelectionChange} />}

      <LinkButton
        variant="ghost"
        size="sm"
        to={getObjectDetailsUrl(objectKind, objectId)}
        className="truncate px-2.5 rounded-full text-custom-blue-700 hover:underline hover:bg-custom-blue-700/10"
      >
        {label}
      </LinkButton>

      <div className="absolute -right-4 top-0 bottom-0 w-4 bg-gradient-to-r from-gray-500/10 pointer-events-none" />
    </TableCell>
  );
}
