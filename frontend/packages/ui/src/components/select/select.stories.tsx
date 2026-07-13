import type { Meta, StoryObj } from "@storybook/react-vite";

import {
  Select,
  SelectItem,
  SelectList,
  SelectTrigger,
  type SelectTriggerProps,
  selectTriggerVariants,
} from "./select";

const SIZES = Object.keys(selectTriggerVariants.variants.size) as SelectTriggerProps["size"][];

const meta: Meta<typeof SelectTrigger> = {
  title: "Components/Select",
  component: SelectTrigger,
  parameters: {
    layout: "centered",
  },
  argTypes: {
    size: { control: "select", options: SIZES },
    isDisabled: { control: "boolean" },
  },
};
export default meta;

type Story = StoryObj<typeof meta>;

const items = [
  { key: "red", label: "Red" },
  { key: "green", label: "Green" },
  { key: "blue", label: "Blue" },
];

const SizeLabel = ({ children }: { children: string }) => (
  <div className="text-xxs font-medium tracking-wider text-neutral-400 uppercase">{children}</div>
);

const ColorSelect = (props: SelectTriggerProps) => (
  <div className="w-64">
    <Select placeholder="Pick a color">
      <SelectTrigger {...props} />
      <SelectList items={items}>
        {(item) => (
          <SelectItem key={item.key} textValue={item.label}>
            {item.label}
          </SelectItem>
        )}
      </SelectList>
    </Select>
  </div>
);

export const AllVariants: Story = {
  argTypes: {
    size: { table: { disable: true } },
  },
  render: ({ isDisabled }) => (
    <div className="flex flex-col gap-4">
      {SIZES.map((size) => (
        <div key={size} className="flex flex-col gap-1">
          <SizeLabel>{size ?? "md"}</SizeLabel>
          <ColorSelect size={size} isDisabled={isDisabled} />
        </div>
      ))}
    </div>
  ),
};

export const Playground: Story = {
  args: {
    size: "md",
    isDisabled: false,
  },
  render: (args) => <ColorSelect {...args} />,
};
