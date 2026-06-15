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
  },
  argTypes: {
    selectionMode: { control: "select", options: ["none", "single", "multiple"] },
    emptyMessage: { control: "text" },
    shouldFocusOnHover: { control: "boolean" },
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

const fruitItems = (selectionIndicator?: "checkmark" | "none") =>
  FRUITS.map((fruit) => (
    <ListBoxItem key={fruit} id={fruit.toLowerCase()} selectionIndicator={selectionIndicator}>
      {fruit}
    </ListBoxItem>
  ));

export const AllVariants: Story = {
  argTypes: {
    selectionMode: { table: { disable: true } },
    emptyMessage: { table: { disable: true } },
    shouldFocusOnHover: { table: { disable: true } },
  },
  render: () => (
    <div className="grid grid-cols-[10rem_auto] items-start gap-x-6 gap-y-4">
      <ColumnLabel>Selection (checkmark)</ColumnLabel>
      <ListBox
        aria-label="Selection with checkmark"
        className="max-w-64"
        selectionMode="single"
        selectedKeys={["banana"]}
      >
        {fruitItems()}
      </ListBox>

      <ColumnLabel>Selection (no checkmark)</ColumnLabel>
      <ListBox
        aria-label="Selection without checkmark"
        className="max-w-64"
        selectionMode="single"
        selectedKeys={["banana"]}
      >
        {fruitItems("none")}
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

type PlaygroundArgs = ListBoxProps<object> & { selectionIndicator?: "checkmark" | "none" };

function PlaygroundRender({ selectionIndicator, ...args }: PlaygroundArgs) {
  return (
    <ListBox {...args} aria-label="Playground" className="min-w-48">
      {fruitItems(selectionIndicator)}
    </ListBox>
  );
}

export const Playground: StoryObj<PlaygroundArgs> = {
  args: {
    selectionIndicator: "checkmark",
  },
  argTypes: {
    selectionIndicator: { control: "inline-radio", options: ["checkmark", "none"] },
  },
  render: PlaygroundRender,
};
