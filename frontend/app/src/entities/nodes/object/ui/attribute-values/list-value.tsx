import { Button } from "@infrahub/ui";
import { ListIcon } from "lucide-react";
import { useState } from "react";

import { classNames } from "@/shared/utils/common";
import { pluralize } from "@/shared/utils/string";

import type { ListElement } from "@/entities/nodes/object/domain/model/list-element";
import { getListElements } from "@/entities/nodes/object/domain/rules/get-list-elements";
import { ListElementChip } from "@/entities/nodes/object/ui/attribute-values/list-element-chip";
import { ListElementsTable } from "@/entities/nodes/object/ui/attribute-values/list-elements-table";
import { useIsOverflowing } from "@/entities/nodes/object/ui/attribute-values/use-is-overflowing";
import { ValueDialog } from "@/entities/nodes/object/ui/attribute-values/value-dialog";

/** More chips than fit in the widest table column, which the cell clips at its edge. */
const LIST_CELL_MAX_CHIPS = 8;
/** Chips the detail view shows before "View all", so a long list stays a few lines tall. */
const LIST_DETAIL_MAX_CHIPS = 10;

export interface ListValueProps {
  values: unknown[];
  attributeLabel: string;
}

function ListDialog({
  elements,
  attributeLabel,
  onClose,
}: {
  elements: ListElement[];
  attributeLabel: string;
  onClose: () => void;
}) {
  return (
    <ValueDialog
      title={attributeLabel}
      subtitle={pluralize(elements.length, "element")}
      copyLabel={`Copy all ${elements.length}`}
      copyData={() => elements.map((element) => element.text).join("\n")}
      onClose={onClose}
    >
      <ListElementsTable elements={elements} attributeLabel={attributeLabel} />
    </ValueDialog>
  );
}

/** A list in a table cell: chips clipped at the cell edge, and a count that opens every element. */
export function ListValueCell({ values, attributeLabel }: ListValueProps) {
  const [isOpen, setIsOpen] = useState(false);
  const { ref, isOverflowing } = useIsOverflowing<HTMLSpanElement>();
  const elements = getListElements(values);

  return (
    <span className="flex min-w-0 items-center gap-1">
      <span
        ref={ref}
        className={classNames(
          "flex min-w-0 items-center gap-1 overflow-hidden",
          isOverflowing && "mask-r-from-85%"
        )}
      >
        {elements.slice(0, LIST_CELL_MAX_CHIPS).map((element) => (
          <ListElementChip key={element.position} element={element} isLink={false} />
        ))}
      </span>

      {elements.length > 1 && (
        <Button
          variant="ghost"
          size="xxs"
          className="shrink-0 text-foreground-muted tabular-nums"
          onPress={() => setIsOpen(true)}
          aria-label={`View all ${elements.length} elements of ${attributeLabel}`}
        >
          <ListIcon />
          {elements.length}
        </Button>
      )}

      {isOpen && (
        <ListDialog
          elements={elements}
          attributeLabel={attributeLabel}
          onClose={() => setIsOpen(false)}
        />
      )}
    </span>
  );
}

/** A list in the detail view: the first chips, and "View all" when some do not show. */
export function ListValueDetail({ values, attributeLabel }: ListValueProps) {
  const [isOpen, setIsOpen] = useState(false);
  const elements = getListElements(values);

  return (
    <span className="flex flex-wrap items-center gap-1">
      {elements.slice(0, LIST_DETAIL_MAX_CHIPS).map((element) => (
        <ListElementChip key={element.position} element={element} />
      ))}

      {elements.length > LIST_DETAIL_MAX_CHIPS && (
        <Button variant="ghost" size="xxs" onPress={() => setIsOpen(true)}>
          View all {elements.length}
        </Button>
      )}

      {isOpen && (
        <ListDialog
          elements={elements}
          attributeLabel={attributeLabel}
          onClose={() => setIsOpen(false)}
        />
      )}
    </span>
  );
}
