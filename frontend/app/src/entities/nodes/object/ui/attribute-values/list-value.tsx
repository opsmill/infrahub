import { Button } from "@infrahub/ui";
import { ListIcon } from "lucide-react";
import React from "react";

import { useIsOverflowing } from "@/shared/hooks/use-is-overflowing";
import { classNames } from "@/shared/utils/common";
import { pluralize } from "@/shared/utils/string";

import { getListElements } from "@/entities/nodes/object/domain/rules/get-list-elements";
import { ListElementBadge } from "@/entities/nodes/object/ui/attribute-values/list-element-badge";
import { ListElementsTable } from "@/entities/nodes/object/ui/attribute-values/list-elements-table";
import { ValueDialog } from "@/entities/nodes/object/ui/attribute-values/value-dialog";
import { getSchema } from "@/entities/schema/domain/use-cases/get-schema";

/** More badges than fit in the widest table column, which the cell clips at its edge. */
const LIST_CELL_MAX_BADGES = 8;
/** The detail view shows this many badges before "View all", so a long list stays a few lines tall. */
const LIST_DETAIL_MAX_BADGES = 10;

const isKnownKind = (kind: string) => !!getSchema(kind).schema;

export interface ListValueProps {
  values: unknown[];
  attributeLabel: string;
}

function ListElementsDialogBody({ values, attributeLabel }: ListValueProps) {
  return (
    <ListElementsTable
      elements={getListElements(values, isKnownKind)}
      attributeLabel={attributeLabel}
    />
  );
}

function ListElementsDialog({
  values,
  attributeLabel,
  isOpen,
  onOpenChange,
}: ListValueProps & { isOpen: boolean; onOpenChange: (isOpen: boolean) => void }) {
  return (
    <ValueDialog
      isOpen={isOpen}
      onOpenChange={onOpenChange}
      title={attributeLabel}
      subtitle={pluralize(values.length, "element")}
      copyLabel={`Copy all ${values.length}`}
      copyData={() =>
        getListElements(values, isKnownKind)
          .map((element) => element.text)
          .join("\n")
      }
    >
      <ListElementsDialogBody values={values} attributeLabel={attributeLabel} />
    </ValueDialog>
  );
}

export function ListValueCell({ values, attributeLabel }: ListValueProps) {
  const [isOpen, setIsOpen] = React.useState(false);
  const { ref, isOverflowing } = useIsOverflowing<HTMLSpanElement>();

  return (
    <span className="flex min-w-0 items-center gap-1">
      <span
        ref={ref}
        className={classNames(
          "flex min-w-0 items-center gap-1 overflow-hidden",
          isOverflowing && "mask-r-from-85%"
        )}
      >
        {getListElements(values.slice(0, LIST_CELL_MAX_BADGES), isKnownKind).map((element) => (
          <ListElementBadge
            key={element.position}
            element={element}
            isLink={false}
            className="max-w-40 shrink-0"
          />
        ))}
      </span>

      <Button
        variant="ghost"
        size="xxs"
        className="shrink-0 text-foreground-muted tabular-nums"
        onPress={() => setIsOpen(true)}
        aria-label={`View all ${pluralize(values.length, "element")} of ${attributeLabel}`}
      >
        <ListIcon />
        {values.length}
      </Button>

      <ListElementsDialog
        values={values}
        attributeLabel={attributeLabel}
        isOpen={isOpen}
        onOpenChange={setIsOpen}
      />
    </span>
  );
}

export function ListValueDetail({ values, attributeLabel }: ListValueProps) {
  const [isOpen, setIsOpen] = React.useState(false);
  const shownElements = getListElements(values.slice(0, LIST_DETAIL_MAX_BADGES), isKnownKind);
  const hasHiddenContent =
    values.length > LIST_DETAIL_MAX_BADGES ||
    shownElements.some((element) => element.type === "Object" || element.type === "Array");

  return (
    <span className="flex min-w-0 flex-wrap items-center gap-1">
      {shownElements.map((element) => (
        <ListElementBadge
          key={element.position}
          element={element}
          isTruncated={element.type === "Object" || element.type === "Array"}
          className="max-w-full"
        />
      ))}

      {hasHiddenContent && (
        <Button
          variant="ghost"
          size="xxs"
          onPress={() => setIsOpen(true)}
          aria-label={`View all ${pluralize(values.length, "element")} of ${attributeLabel}`}
        >
          View all {values.length}
        </Button>
      )}

      <ListElementsDialog
        values={values}
        attributeLabel={attributeLabel}
        isOpen={isOpen}
        onOpenChange={setIsOpen}
      />
    </span>
  );
}
