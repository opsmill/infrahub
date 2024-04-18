import React from "react";
import TreeViewPrimitive, { ITreeViewProps, INodeRendererProps } from "react-accessible-treeview";
import { Icon } from "@iconify-icon/react";
import { classNames } from "../../utils/common";

export type TreeItemProps = Pick<INodeRendererProps, "element">;

export interface TreeProps extends Omit<ITreeViewProps, "nodeRenderer"> {
  itemContent?: (props: TreeItemProps) => React.ReactNode;
}

export const Tree = ({ itemContent, ...props }: TreeProps) => {
  const NodeComp = itemContent || DefaultTreeItem;
  return (
    <TreeViewPrimitive
      {...props}
      nodeRenderer={(nodeRendererProps) => (
        <TreeItemWrapper {...nodeRendererProps}>
          {nodeRendererProps.isBranch ? (
            <Icon
              icon={nodeRendererProps.isExpanded ? "mdi:chevron-down" : "mdi:chevron-right"}
              onClick={nodeRendererProps.handleExpand}
              className="px-1.5"
            />
          ) : (
            <div className="w-7" />
          )}
          {<NodeComp element={nodeRendererProps.element} />}
        </TreeItemWrapper>
      )}
      className={classNames(
        "border rounded-md p-2",
        "[&_li:focus]:rounded-md [&_li:focus]:outline-none [&_li:focus]:ring-2 [&_li:focus]:ring-custom-blue-500 [&_li:focus]:ring-offset-2"
      )}
    />
  );
};

const TreeItemWrapper = (props: INodeRendererProps & { children: React.ReactNode }) => {
  const { children, getNodeProps, isSelected, level } = props;
  return (
    <div
      {...getNodeProps()}
      style={{ marginLeft: (level - 1) * 20 }}
      className={classNames(
        "flex items-center",
        "text-gray-600 mix-blend-multiply",
        "h-8 rounded-md cursor-pointer",
        "focus-visible:outline-none focus:ring-2 focus:ring-custom-blue-500 focus:ring-offset-2",
        isSelected ? "bg-custom-blue-500 text-custom-white" : "hover:bg-custom-blue-400"
      )}>
      {children}
    </div>
  );
};

const DefaultTreeItem: React.FC<TreeItemProps> = ({ element }) => {
  return <span>{element.name}</span>;
};
