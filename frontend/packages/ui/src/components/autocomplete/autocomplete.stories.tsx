import type { Meta, StoryObj } from "@storybook/react-vite";

import { PlusIcon } from "lucide-react";

import { Button } from "../button/button";
import { ListBox, ListBoxItem } from "../list-box/list-box";
import { Autocomplete } from "./autocomplete";

const meta: Meta<typeof Autocomplete> = {
  title: "Components/Autocomplete",
  component: Autocomplete,
};
export default meta;

type Story = StoryObj<typeof Autocomplete>;

const fruits = ["Apple", "Banana", "Cherry", "Date", "Elderberry", "Fig", "Grape"];

export const Default: Story = {
  render: () => (
    <div className="w-64 rounded-lg border border-neutral-300">
      <Autocomplete
        suffix={
          <Button variant="ghost" shape="square" size="xxs">
            <PlusIcon />
          </Button>
        }
      >
        <ListBox aria-label="Fruits" className="max-h-60 p-1" emptyMessage="No result found">
          {fruits.map((fruit) => (
            <ListBoxItem key={fruit} textValue={fruit}>
              {fruit}
            </ListBoxItem>
          ))}
        </ListBox>
      </Autocomplete>
    </div>
  ),
};
