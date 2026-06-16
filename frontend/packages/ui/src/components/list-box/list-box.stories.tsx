import type { Meta, StoryObj } from "@storybook/react-vite";
import type React from "react";

import { ListBox, ListBoxItem, type ListBoxProps } from "./list-box";

const meta: Meta<typeof ListBox> = {
  component: ListBox,
  parameters: {
    layout: "centered",
  },
  args: {
    selectionMode: "single",
    emptyMessage: "No results found.",
    shouldFocusOnHover: true,
    selectionIndicator: "checkmark",
  },
  argTypes: {
    selectionMode: { control: "select", options: ["none", "single", "multiple"] },
    emptyMessage: { control: "text" },
    shouldFocusOnHover: { control: "boolean" },
    selectionIndicator: { control: "inline-radio", options: ["checkmark", "highlight", "none"] },
  },
};

export default meta;

type Story = StoryObj<typeof meta>;

const ColumnLabel = ({ children }: { children: React.ReactNode }) => (
  <div className="font-medium text-[10px] text-neutral-400 uppercase tracking-wider">
    {children}
  </div>
);

const FRUITS = ["Apple", "Banana", "Cherry"];

// Items inherit the selection indicator from the <ListBox> via context.
const fruitItems = () =>
  FRUITS.map((fruit) => (
    <ListBoxItem key={fruit} id={fruit.toLowerCase()}>
      {fruit}
    </ListBoxItem>
  ));

export const AllVariants: Story = {
  argTypes: {
    selectionMode: { table: { disable: true } },
    emptyMessage: { table: { disable: true } },
    shouldFocusOnHover: { table: { disable: true } },
    selectionIndicator: { table: { disable: true } },
  },
  render: () => (
    <div className="grid grid-cols-[10rem_auto] items-start gap-x-6 gap-y-4">
      <ColumnLabel>Selection (checkmark)</ColumnLabel>
      <ListBox
        aria-label="Selection with checkmark"
        className="max-w-64"
        selectionMode="single"
        selectedKeys={["banana"]}
        selectionIndicator="checkmark"
      >
        {fruitItems()}
      </ListBox>

      <ColumnLabel>Selection (highlight)</ColumnLabel>
      <ListBox
        aria-label="Selection with highlight"
        className="max-w-64"
        selectionMode="single"
        selectedKeys={["banana"]}
        selectionIndicator="highlight"
      >
        {fruitItems()}
      </ListBox>

      <ColumnLabel>Selection (none)</ColumnLabel>
      <ListBox
        aria-label="Selection without indicator"
        className="max-w-64"
        selectionMode="single"
        selectedKeys={["banana"]}
        selectionIndicator="none"
      >
        {fruitItems()}
      </ListBox>

      <ColumnLabel>Disabled item</ColumnLabel>
      <ListBox
        aria-label="Disabled item"
        className="max-w-64"
        selectionMode="single"
        disabledKeys={["banana"]}
      >
        {fruitItems()}
      </ListBox>

      <ColumnLabel>Empty state</ColumnLabel>
      <ListBox aria-label="Empty" className="max-w-64" emptyMessage="No results found." />
    </div>
  ),
  parameters: {
    layout: "padded",
  },
};

function PlaygroundRender(args: ListBoxProps<object>) {
  return (
    <ListBox {...args} aria-label="Playground" className="min-w-48">
      {fruitItems()}
    </ListBox>
  );
}

export const Playground: Story = {
  render: PlaygroundRender,
};
