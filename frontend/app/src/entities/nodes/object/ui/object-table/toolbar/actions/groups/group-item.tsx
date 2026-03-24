import { composeRenderProps, ListBoxItem, type ListBoxItemProps } from "react-aria-components";

import { focusVisibleStyle } from "@/shared/components/aria/style-rac";
import { classNames } from "@/shared/utils/common";

import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import type { RelationshipNode } from "@/entities/nodes/relationships/domain/types";

export interface GroupItemProps extends ListBoxItemProps {
  group: RelationshipNode;
}

export function GroupItem({ group, children, className, ...props }: GroupItemProps) {
  const label = getNodeLabel(group);

  return (
    <ListBoxItem
      className={classNames(
        focusVisibleStyle,
        "inline-flex max-w-full items-center overflow-hidden rounded-full bg-stone-100 px-1 py-0.5 text-sm",
        "border border-stone-100 transition-all",
        className
      )}
      textValue={label}
      {...props}
    >
      {composeRenderProps(children, (children) => (
        <>
          <span className="truncate px-1.5">{label}</span>
          {children}
        </>
      ))}
    </ListBoxItem>
  );
}
