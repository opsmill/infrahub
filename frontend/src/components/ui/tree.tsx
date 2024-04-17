import React from "react";
import TreeViewPrimitive, { ITreeViewProps, INodeRendererProps } from "react-accessible-treeview";
import { Icon } from "@iconify-icon/react";
import { classNames } from "../../utils/common";

export interface TreeProps extends Omit<ITreeViewProps, "nodeRenderer"> {
  nodeRenderer?: (props: INodeRendererProps) => React.ReactNode;
}

export const Tree = (props: TreeProps) => {
  return (
    <TreeViewPrimitive
      {...props}
      nodeRenderer={props.nodeRenderer ?? TreeItem}
      className={classNames(
        "border rounded-md p-2",
        "[&_li:focus]:rounded-md [&_li:focus]:outline-none [&_li:focus]:ring-2 [&_li:focus]:ring-custom-blue-500 [&_li:focus]:ring-offset-2"
      )}
    />
  );
};

export const TreeItem = ({
  element,
  getNodeProps,
  handleExpand,
  handleSelect,
  isBranch,
  isSelected,
  isExpanded,
  level,
}: INodeRendererProps) => {
  return (
    <div
      {...getNodeProps({
        onClick: handleSelect,
      })}
      style={{ marginLeft: (level - 1) * 20 }}
      className={classNames(
        "flex items-center",
        "text-gray-600 mix-blend-multiply",
        "h-8 rounded-md cursor-pointer",
        "focus-visible:outline-none focus:ring-2 focus:ring-custom-blue-500 focus:ring-offset-2",
        isSelected ? "bg-custom-blue-500 text-custom-white" : "hover:bg-custom-blue-400"
      )}>
      {isBranch ? (
        <Icon
          icon={isExpanded ? "mdi:chevron-down" : "mdi:chevron-right"}
          onClick={handleExpand}
          className="px-1.5"
        />
      ) : (
        <div className="px-1.5" />
      )}
      <span>{element.name}</span>
    </div>
  );
};
