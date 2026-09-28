import type { Meta, StoryObj } from "@storybook/react-vite";
import { ReactFlowProvider } from "@xyflow/react";

import { Toolbar } from "../toolbar/toolbar";
import { GraphControls } from "./graph-controls";

const meta: Meta<typeof GraphControls> = {
  title: "Graph/GraphControls",
  component: GraphControls,
};
export default meta;

type Story = StoryObj<typeof GraphControls>;

export const Default: Story = {
  render: () => (
    <ReactFlowProvider>
      <Toolbar aria-label="Graph controls">
        <GraphControls edgeStyle="bezier" onEdgeStyleChange={() => {}} onLayout={() => {}} />
      </Toolbar>
    </ReactFlowProvider>
  ),
};
