import type { Meta, StoryObj } from "@storybook/react-vite";

import { Meter } from "./meter";

const meta: Meta<typeof Meter> = {
  component: Meter,
  parameters: {
    layout: "padded",
  },
  args: {
    value: 42,
    "aria-label": "Example meter",
  },
  argTypes: {
    value: { control: { type: "range", min: 0, max: 100, step: 1 } },
  },
};

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {
  render: (args) => (
    <div className="w-80">
      <Meter {...args} />
    </div>
  ),
};

export const WithLabel: Story = {
  args: {
    label: "Disk usage",
  },
  render: (args) => (
    <div className="w-80">
      <Meter {...args} />
    </div>
  ),
};

export const CustomFormat: Story = {
  args: {
    label: "Storage",
    value: 1500,
    minValue: 0,
    maxValue: 2000,
    formatOptions: {
      style: "unit",
      unit: "megabyte",
      maximumFractionDigits: 0,
    },
  },
  render: (args) => (
    <div className="w-80">
      <Meter {...args} />
    </div>
  ),
};

export const Playground: Story = {
  args: {
    label: "Playground",
    value: 60,
  },
  render: (args) => (
    <div className="w-80">
      <Meter {...args} />
    </div>
  ),
};
