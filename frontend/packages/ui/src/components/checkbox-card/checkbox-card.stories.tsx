import type { Meta, StoryObj } from "@storybook/react-vite";
import { type ComponentProps, useState } from "react";

import { CheckboxCard } from "./checkbox-card";

const meta: Meta<typeof CheckboxCard> = {
  component: CheckboxCard,
  parameters: {
    layout: "centered",
  },
  args: {
    children: "Apple",
    isSelected: false,
    isDisabled: false,
  },
  argTypes: {
    children: { control: "text" },
    isSelected: { control: "boolean" },
    isDisabled: { control: "boolean" },
  },
};

export default meta;

type Story = StoryObj<typeof meta>;

const FRUITS = ["Apple", "Banana", "Cherry"] as const;

function DefaultRender() {
  const [selectedFruits, setSelectedFruits] = useState<string[]>(["Banana"]);

  const toggleFruit = (fruit: string) => {
    setSelectedFruits((current) =>
      current.includes(fruit) ? current.filter((item) => item !== fruit) : [...current, fruit]
    );
  };

  return (
    <div className="grid w-96 grid-cols-3 gap-2">
      {FRUITS.map((fruit) => (
        <CheckboxCard
          key={fruit}
          isSelected={selectedFruits.includes(fruit)}
          onChange={() => toggleFruit(fruit)}
        >
          {fruit}
        </CheckboxCard>
      ))}
    </div>
  );
}

function PlaygroundRender(args: ComponentProps<typeof CheckboxCard>) {
  return (
    <div className="w-72">
      <CheckboxCard {...args} />
    </div>
  );
}

export const Default: Story = {
  argTypes: {
    isSelected: { table: { disable: true } },
    isDisabled: { table: { disable: true } },
    children: { table: { disable: true } },
  },
  render: DefaultRender,
};

export const Playground: Story = {
  render: PlaygroundRender,
};
