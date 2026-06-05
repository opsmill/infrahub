import type { Meta, StoryObj } from "@storybook/react-vite";
import { Collection, type TreeProps } from "react-aria-components";

import { Tree, TreeItem, TreeItemContent, TreeItemLoader } from "./tree";

type FolderNode = {
  id: string;
  name: string;
  children?: FolderNode[];
};

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

function WithLoaderRender() {
  return (
    <Tree
      aria-label="Project files (loading)"
      items={TREE_DATA}
      defaultExpandedKeys={["docs", "src"]}
      className="w-72"
    >
      {(item) => (
        <TreeItem id={item.id} textValue={item.name}>
          <TreeItemContent>{item.name}</TreeItemContent>
          <Collection items={item.children ?? []}>{renderItem}</Collection>
          {item.id === "src" && <TreeItemLoader />}
        </TreeItem>
      )}
    </Tree>
  );
}

function PlaygroundRender(args: Omit<TreeProps<FolderNode>, "children" | "items">) {
  return (
    <Tree {...args} items={TREE_DATA} className="w-72">
      {renderItem}
    </Tree>
  );
}

export const Default: Story = {
  render: DefaultRender,
};

export const WithLoader: Story = {
  render: WithLoaderRender,
};

export const Playground: Story = {
  args: {
    "aria-label": "Project files",
    selectionMode: "single",
    defaultExpandedKeys: ["docs", "src"],
  },
  argTypes: {
    "aria-label": { control: "text" },
    selectionMode: {
      control: "select",
      options: ["none", "single", "multiple"],
    },
  },
  render: PlaygroundRender,
};
