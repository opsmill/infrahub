import React from "react";
import TreeViewPrimitive, { ITreeViewProps, INodeRendererProps } from "react-accessible-treeview";
import { Icon } from "@iconify-icon/react";

export interface TreeProps extends Omit<ITreeViewProps, "nodeRenderer"> {
  nodeRenderer?: (props: INodeRendererProps) => React.ReactNode;
}

export const Tree = (props: TreeProps) => {
  return <TreeViewPrimitive {...props} nodeRenderer={props.nodeRenderer ?? TreeItem} />;
};

export const TreeItem = ({
  element,
  getNodeProps,
  handleExpand,
  isBranch,
  isExpanded,
  level,
}: INodeRendererProps) => {
  return (
    <div
      {...getNodeProps({ onClick: handleExpand })}
      style={{ marginLeft: (level - 1) * 24 }}
      className="flex items-center gap-2 hover:bg-gray-100 cursor-pointer px-2 py-1.5 rounded-md text-gray-600">
      {isBranch && <Icon icon={isExpanded ? "mdi:chevron-down" : "mdi:chevron-right"} />}
      {element.name}
    </div>
  );
};
