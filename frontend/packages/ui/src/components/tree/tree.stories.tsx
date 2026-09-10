import type { Meta, StoryObj } from "@storybook/react-vite";
import { Collection } from "react-aria-components";

import { Tree, TreeItem, TreeItemContent } from "./tree";

interface FolderNode {
  id: string;
  name: string;
  children?: FolderNode[];
}

const TREE_DATA: FolderNode[] = [
  {
    id: "docs",
    name: "docs",
    children: [
      { id: "docs/readme", name: "README.md" },
      { id: "docs/getting-started", name: "getting-started.md" },
    ],
  },
  {
    id: "src",
    name: "src",
    children: [
      {
        id: "src/components",
        name: "components",
        children: [
          { id: "src/components/button.tsx", name: "button.tsx" },
          { id: "src/components/card.tsx", name: "card.tsx" },
        ],
      },
      { id: "src/index.ts", name: "index.ts" },
    ],
  },
];

const meta: Meta<typeof Tree> = {
  component: Tree,
  parameters: {
    layout: "centered",
  },
};

export default meta;

type Story = StoryObj<typeof meta>;

function renderItem(item: FolderNode) {
  return (
    <TreeItem id={item.id} textValue={item.name}>
      <TreeItemContent>{item.name}</TreeItemContent>
      <Collection items={item.children ?? []}>{renderItem}</Collection>
    </TreeItem>
  );
}

function DefaultRender() {
  return (
    <Tree
      aria-label="Project files"
      items={TREE_DATA}
      defaultExpandedKeys={["docs", "src", "src/components"]}
      className="w-72"
    >
      {renderItem}
    </Tree>
  );
}

export const Default: Story = {
  render: DefaultRender,
};
