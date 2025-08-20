import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { RelationshipNode } from "@/entities/nodes/relationships/domain/types";
import { focusVisibleStyle } from "@/shared/components/style-rac";
import { classNames } from "@/shared/utils/common";
import { ListBoxItem, ListBoxItemProps, composeRenderProps } from "react-aria-components";

export interface GroupItemProps extends ListBoxItemProps {
  group: RelationshipNode;
}

export function GroupItem({ group, children, className, ...props }: GroupItemProps) {
  const label = getNodeLabel(group);

  return (
    <ListBoxItem
      className={classNames(
        focusVisibleStyle,
        "inline-flex items-center px-1 py-0.5 text-sm bg-stone-100 rounded-full overflow-hidden max-w-full",
        "transition-all border border-stone-100",
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
