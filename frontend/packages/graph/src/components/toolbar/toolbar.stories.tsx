import { Button } from "@infrahub/ui";
import type { Meta, StoryObj } from "@storybook/react-vite";
import { Minus, Plus } from "lucide-react";

import { Toolbar } from "./toolbar";

const meta: Meta<typeof Toolbar> = {
  title: "Components/Toolbar",
  component: Toolbar,
};
export default meta;

type Story = StoryObj<typeof Toolbar>;

export const Default: Story = {
  render: () => (
    <Toolbar aria-label="Example controls">
      <Button variant="ghost" size="sm" shape="square" aria-label="Zoom out">
        <Minus />
      </Button>
      <Toolbar.Divider />
      <Button variant="ghost" size="sm" shape="square" aria-label="Zoom in">
        <Plus />
      </Button>
    </Toolbar>
  ),
};
