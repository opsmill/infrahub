import type { Meta, StoryObj } from "@storybook/react-vite";

import { Button } from "../button/button";
import { Popover, PopoverDialog, PopoverTrigger } from "./popover";

const meta: Meta<typeof Popover> = {
  title: "Components/Popover",
  component: Popover,
};
export default meta;

type Story = StoryObj<typeof Popover>;

export const Default: Story = {
  render: () => (
    <PopoverTrigger>
      <Button>Open popover</Button>
      <Popover>
        <PopoverDialog className="p-4">
          <p className="text-sm">This is the popover content.</p>
        </PopoverDialog>
      </Popover>
    </PopoverTrigger>
  ),
};
