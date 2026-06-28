import type { Meta, StoryObj } from "@storybook/react-vite";

import { Select, SelectItem, SelectList, SelectTrigger } from "./select";

const meta: Meta<typeof Select> = {
  title: "Components/Select",
  component: Select,
};
export default meta;

type Story = StoryObj<typeof Select>;

const items = [
  { key: "red", label: "Red" },
  { key: "green", label: "Green" },
  { key: "blue", label: "Blue" },
];

export const Default: Story = {
  render: () => (
    <div className="w-64">
      <Select placeholder="Pick a color">
        <SelectTrigger />
        <SelectList items={items}>
          {(item) => (
            <SelectItem key={item.key} textValue={item.label}>
              {item.label}
            </SelectItem>
          )}
        </SelectList>
      </Select>
    </div>
  ),
};
