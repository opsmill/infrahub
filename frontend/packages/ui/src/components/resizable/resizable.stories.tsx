import type { Meta, StoryObj } from "@storybook/react-vite";

import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "./resizable";

const meta: Meta<typeof ResizablePanelGroup> = {
  component: ResizablePanelGroup,
  parameters: {
    layout: "padded",
  },
};

export default meta;

type Story = StoryObj<typeof meta>;

const PanelContent = ({ label }: { label: string }) => (
  <div className="flex h-full w-full items-center justify-center bg-stone-100 p-3 text-sm text-stone-700">
    {label}
  </div>
);

export const Horizontal: Story = {
  render: () => (
    <div className="h-64 w-[640px] rounded border border-stone-300 overflow-hidden">
      <ResizablePanelGroup>
        <ResizablePanel defaultSize={200} minSize={80}>
          <PanelContent label="Left" />
        </ResizablePanel>
        <ResizableHandle />
        <ResizablePanel defaultSize={400} minSize={80}>
          <PanelContent label="Right" />
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  ),
};

export const Vertical: Story = {
  render: () => (
    <div className="h-64 w-[640px] rounded border border-stone-300 overflow-hidden">
      <ResizablePanelGroup orientation="vertical">
        <ResizablePanel defaultSize={120} minSize={40}>
          <PanelContent label="Top" />
        </ResizablePanel>
        <ResizableHandle />
        <ResizablePanel defaultSize={120} minSize={40}>
          <PanelContent label="Bottom" />
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  ),
};

export const Playground: Story = {
  args: {
    orientation: "horizontal",
  },
  argTypes: {
    orientation: {
      control: "select",
      options: ["horizontal", "vertical"],
    },
  },
  render: (args) => (
    <div className="h-64 w-[640px] rounded border border-stone-300 overflow-hidden">
      <ResizablePanelGroup {...args}>
        <ResizablePanel defaultSize={200} minSize={80}>
          <PanelContent label="Panel A" />
        </ResizablePanel>
        <ResizableHandle />
        <ResizablePanel defaultSize={400} minSize={80}>
          <PanelContent label="Panel B" />
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  ),
};
