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
      nodeRenderer={(props) => (
        <TreeItemWrapper {...props}>
          {props.isBranch ? (
            <Icon
              icon={props.isExpanded ? "mdi:chevron-down" : "mdi:chevron-right"}
              onClick={props.handleExpand}
              className="px-1.5"
            />
          ) : (
            <div className="px-1.5" />
          )}
          <DefaultItem element={props.element} />
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
  const { getNodeProps, isSelected, level } = props;
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
      {props.children}
    </div>
  );
};

type RenderNodeProps = Pick<INodeRendererProps, "element">;

const DefaultItem: React.FC<RenderNodeProps> = ({ element }) => {
  return <span>{element.name}</span>;
};
