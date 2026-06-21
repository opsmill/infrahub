import type { Meta, StoryObj } from "@storybook/react-vite";

import { PlusIcon } from "lucide-react";

import { Button } from "../button/button";
import { ListBox, ListBoxItem } from "../list-box/list-box";
import { Autocomplete } from "./autocomplete";

const meta: Meta<typeof Autocomplete> = {
  title: "Components/Autocomplete",
  component: Autocomplete,
  parameters: {
    layout: "centered",
  },
};
export default meta;

type Story = StoryObj<typeof Autocomplete>;

const fruits = ["Apple", "Banana", "Cherry", "Date", "Elderberry", "Fig", "Grape"];

const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="w-64 overflow-hidden rounded-lg border border-neutral-300">{children}</div>
);

const fruitList = () => (
  <ListBox aria-label="Fruits" className="max-h-60 p-1" emptyMessage="No result found">
    {fruits.map((fruit) => (
      <ListBoxItem key={fruit} textValue={fruit}>
        {fruit}
      </ListBoxItem>
    ))}
  </ListBox>
);

export const Default: Story = {
  render: () => (
    <div className="flex gap-8">
      <Frame>
        <Autocomplete>{fruitList()}</Autocomplete>
      </Frame>

      <Frame>
        <Autocomplete
          suffix={
            <Button variant="ghost" shape="square" size="xxs">
              <PlusIcon />
            </Button>
          }
        >
          {fruitList()}
        </Autocomplete>
      </Frame>
    </div>
  ),
};
