import React from "react";
import TreeViewPrimitive, { ITreeViewProps, INodeRendererProps } from "react-accessible-treeview";
import { Icon } from "@iconify-icon/react";
import { classNames } from "../../utils/common";

export type TreeItemProps = Pick<INodeRendererProps, "element">;

export interface TreeProps extends Omit<ITreeViewProps, "nodeRenderer"> {
  itemContent?: (props: TreeItemProps) => React.ReactNode;
}

export const Tree = ({ itemContent, className, ...props }: TreeProps) => {
  const NodeComp = itemContent || DefaultTreeItem;
  return (
    <TreeViewPrimitive
      propagateSelectUpwards
      {...props}
      nodeRenderer={(nodeRendererProps) => (
        <TreeItemWrapper {...nodeRendererProps}>
          <NodeComp element={nodeRendererProps.element} />
        </TreeItemWrapper>
      )}
      className={classNames(
        "border rounded text-sm",
        "[&_li:focus-visible]:rounded [&_li:focus-visible]:outline-none [&_li:focus-visible]:ring-2 [&_li:focus-visible]:ring-custom-blue-500 [&_li:focus-visible]:ring-offset-2",
        className
      )}
    />
  );
};

const TreeItemWrapper = (props: INodeRendererProps & { children: React.ReactNode }) => {
  const { children, getNodeProps, isBranch, isExpanded, isSelected, isHalfSelected, level } = props;
  return (
    <div
      {...getNodeProps()}
      style={{ paddingLeft: (level - 1) * 20 }}
      className={classNames(
        "flex items-center",
        "text-gray-600 mix-blend-multiply",
        "h-8 px-1.5 cursor-pointer",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-custom-blue-500 focus-visible:rounded",
        isSelected ? "bg-gray-200" : "hover:bg-gray-100",
        isHalfSelected && "bg-gray-50"
      )}>
      {isBranch ? (
        <Icon icon={isExpanded ? "mdi:chevron-down" : "mdi:chevron-right"} className="px-1.5" />
      ) : (
        <DotIcon />
      )}
      {children}
    </div>
  );
};

const DefaultTreeItem: React.FC<TreeItemProps> = ({ element }) => {
  return <span className="truncate">{element.name}</span>;
};

const DotIcon = () => (
  <svg
    width="26"
    height="6"
    viewBox="0 0 6 6"
    fill="currentColor"
    xmlns="http://www.w3.org/2000/svg">
    <path
      fillRule="evenodd"
      clipRule="evenodd"
      d="M2.9999 4.3C3.71787 4.3 4.2999 3.71797 4.2999 3C4.2999 2.28203 3.71787 1.7 2.9999 1.7C2.28193 1.7 1.6999 2.28203 1.6999 3C1.6999 3.71797 2.28193 4.3 2.9999 4.3ZM2.9999 5.1C4.1597 5.1 5.0999 4.1598 5.0999 3C5.0999 1.8402 4.1597 0.900002 2.9999 0.900002C1.8401 0.900002 0.899902 1.8402 0.899902 3C0.899902 4.1598 1.8401 5.1 2.9999 5.1Z"
    />
  </svg>
);
