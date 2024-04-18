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
              className="px-1.5"
            />
          ) : (
            <div className="w-7" />
          )}
          {<NodeComp element={nodeRendererProps.element} />}
        </TreeItemWrapper>
      )}
      className={classNames(
        "border rounded p-2",
        "[&_li:focus-visible]:rounded [&_li:focus-visible]:outline-none [&_li:focus-visible]:ring-2 [&_li:focus-visible]:ring-sky-300 [&_li:focus-visible]:ring-offset-2"
      )}
    />
  );
};

const TreeItemWrapper = (props: INodeRendererProps & { children: React.ReactNode }) => {
  const { children, getNodeProps, isSelected, level } = props;
  return (
    <div
      {...getNodeProps()}
      style={{ paddingLeft: (level - 1) * 20 }}
      className={classNames(
        "flex items-center",
        "text-gray-600",
        "h-8 px-1.5 rounded cursor-pointer",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-300",
        isSelected ? "bg-sky-300" : "hover:bg-sky-100"
      )}>
      {children}
    </div>
  );
};

const DefaultTreeItem: React.FC<TreeItemProps> = ({ element }) => {
  return <span>{element.name}</span>;
};
