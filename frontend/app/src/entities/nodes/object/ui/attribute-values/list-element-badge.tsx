import { Badge } from "@/shared/components/ui/badge";
import { classNames } from "@/shared/utils/common";

import type { ListElement } from "@/entities/nodes/object/domain/model/list-element";
import { RelationshipNodeDisplay } from "@/entities/nodes/object/ui/object-table/cells/table-relationship-cell";

export interface ListElementBadgeProps {
  element: ListElement;
  isLink?: boolean;
  isTruncated?: boolean;
  className?: string;
}

export function ListElementBadge({
  element,
  isLink,
  isTruncated = true,
  className,
}: ListElementBadgeProps) {
  if (element.type === "Node") {
    return (
      <RelationshipNodeDisplay
        node={element.value}
        size="xxs"
        isLink={isLink}
        className={classNames("min-w-0", className)}
      />
    );
  }

  return (
    <Badge
      variant="gray"
      className={classNames("min-w-0 font-normal", className)}
      title={element.text}
    >
      <span className={isTruncated ? "truncate" : "wrap-anywhere"}>{element.text}</span>
    </Badge>
  );
}
