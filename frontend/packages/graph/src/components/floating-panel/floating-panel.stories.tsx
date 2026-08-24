import type { Meta, StoryObj } from "@storybook/react-vite";

import { FloatingPanel } from "./floating-panel";

const meta: Meta<typeof FloatingPanel> = {
  title: "Components/FloatingPanel",
  component: FloatingPanel,
};
export default meta;

type Story = StoryObj<typeof FloatingPanel>;

export const Default: Story = {
  args: {
    title: "Path Traversal",
    description: "Find paths between two objects in the graph.",
    className: "w-80",
    children: <div className="p-4 text-sm">Panel body</div>,
  },
};
