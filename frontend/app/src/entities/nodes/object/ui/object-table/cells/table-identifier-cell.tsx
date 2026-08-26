import { Checkbox, LinkButton, Tooltip } from "@infrahub/ui";
import type { PressEvent } from "react-aria-components";

import type { overrideQueryParams } from "@/shared/api/rest/fetch";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import { StickyLeftCell } from "@/entities/nodes/object/ui/object-table/cells/style";
import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";

export interface TableIdentifierCellProps {
  objectKind: string;
  objectId: string;
  label: React.ReactNode;
  isSelected?: boolean;
  onClickCheckbox?: (e: PressEvent) => void;
  overrideParams?: overrideQueryParams[];
}

export function TableIdentifierCell({
  objectKind,
  objectId,
  label,
  isSelected,
  onClickCheckbox,
  overrideParams,
}: TableIdentifierCellProps) {
  const { isAuthenticated } = useAuth();

  return (
    <StickyLeftCell data-testid="identifier-cell">
      {isAuthenticated && <Checkbox isSelected={isSelected} onPress={onClickCheckbox} />}

      {/* The label is truncated to keep the sticky column from covering the row
          actions, so surface the full value on hover. `Tooltip` renders its children
          untouched when `message` is empty, which covers non-string labels. */}
      <Tooltip message={typeof label === "string" ? label : undefined}>
        <LinkButton
          variant="ghost"
          size="sm"
          href={getObjectDetailsUrl(objectKind, objectId, overrideParams)}
          className="-mx-1 min-w-0 shrink rounded-xl px-2 text-custom-blue-700 hover:underline"
        >
          {/* The button is a flex container, where `text-overflow` has no effect, so
              the ellipsis has to live on a child of it. */}
          <span className="truncate">{label}</span>
        </LinkButton>
      </Tooltip>
    </StickyLeftCell>
  );
}
