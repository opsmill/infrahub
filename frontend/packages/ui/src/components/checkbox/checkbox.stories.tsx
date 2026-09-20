import type { Meta, StoryObj } from "@storybook/react-vite";
import { type ComponentProps, useState } from "react";

import { Checkbox } from "./checkbox";

const meta: Meta<typeof Checkbox> = {
  component: Checkbox,
  parameters: {
    layout: "centered",
  },
  args: {
    children: "Accept terms",
    isSelected: false,
    isIndeterminate: false,
    isDisabled: false,
  },
  argTypes: {
    children: { control: "text" },
    isSelected: { control: "boolean" },
    isIndeterminate: { control: "boolean" },
    isDisabled: { control: "boolean" },
  },
};

export default meta;

type Story = StoryObj<typeof meta>;

function DefaultRender() {
  const [isSelected, setIsSelected] = useState(false);

  return (
    <Checkbox isSelected={isSelected} onChange={setIsSelected}>
      Accept terms
    </Checkbox>
  );
}

function PlaygroundRender(args: ComponentProps<typeof Checkbox>) {
  return <Checkbox {...args} />;
}

export const Default: Story = {
  argTypes: {
    isSelected: { table: { disable: true } },
    isIndeterminate: { table: { disable: true } },
    isDisabled: { table: { disable: true } },
    children: { table: { disable: true } },
  },
  render: DefaultRender,
};

export const Playground: Story = {
  render: PlaygroundRender,
};
