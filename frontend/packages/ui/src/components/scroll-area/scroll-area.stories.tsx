import type { Meta, StoryObj } from "@storybook/react-vite";

import { ScrollArea } from "./scroll-area";

const VERTICAL_ITEM_COUNT = 30;
const HORIZONTAL_ITEM_COUNT = 30;
const BOTH_ITEM_COUNT = 100;

const verticalIndices = Array.from({ length: VERTICAL_ITEM_COUNT }, (_value, index) => index);
const horizontalIndices = Array.from({ length: HORIZONTAL_ITEM_COUNT }, (_value, index) => index);
const bothIndices = Array.from({ length: BOTH_ITEM_COUNT }, (_value, index) => index);

const meta: Meta<typeof ScrollArea> = {
  component: ScrollArea,
  parameters: {
    layout: "padded",
  },
};

export default meta;

type Story = StoryObj<typeof meta>;

function VerticalContent() {
  return (
    <div className="space-y-1 p-3 text-sm">
      {verticalIndices.map((index) => (
        <div key={index}>Item {index}</div>
      ))}
    </div>
  );
}

function HorizontalContent() {
  return (
    <div className="flex gap-2 p-3">
      {horizontalIndices.map((index) => (
        <div
          key={index}
          className="flex h-16 w-32 shrink-0 items-center justify-center rounded border border-border-strong bg-stone-100 text-sm"
        >
          Item {index}
        </div>
      ))}
    </div>
  );
}

function BothContent() {
  return (
    <div className="grid grid-cols-10 gap-2 p-3" style={{ width: "800px" }}>
      {bothIndices.map((index) => (
        <div
          key={index}
          className="flex h-16 w-20 items-center justify-center rounded border border-border-strong bg-stone-100 text-sm"
        >
          {index}
        </div>
      ))}
    </div>
  );
}

export const Default: Story = {
  render: () => (
    <div className="flex gap-4">
      <div className="rounded border border-border-strong">
        <p className="px-3 py-2 font-medium text-subtle text-xs">Both</p>
        <ScrollArea scrollX scrollY className="h-48 w-64">
          <BothContent />
        </ScrollArea>
      </div>
      <div className="rounded border border-border-strong">
        <p className="px-3 py-2 font-medium text-subtle text-xs">Vertical</p>
        <ScrollArea className="h-48 w-64">
          <VerticalContent />
        </ScrollArea>
      </div>
      <div className="rounded border border-border-strong">
        <p className="px-3 py-2 font-medium text-subtle text-xs">Horizontal</p>
        <ScrollArea scrollX scrollY={false} className="h-48 w-64">
          <HorizontalContent />
        </ScrollArea>
      </div>
    </div>
  ),
};

export const Playground: Story = {
  args: {
    scrollX: true,
    scrollY: true,
  },
  argTypes: {
    scrollX: { control: "boolean" },
    scrollY: { control: "boolean" },
  },
  render: (args) => (
    <div className="rounded border border-border-strong">
      <ScrollArea {...args} className="h-64 w-64">
        <BothContent />
      </ScrollArea>
    </div>
  ),
};
