import type { Meta, StoryObj } from "@storybook/react-vite";
import { Minus, Plus } from "lucide-react";

import { IconButton } from "../icon-button/icon-button";
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
      <IconButton aria-label="Zoom out">
        <Minus />
      </IconButton>
      <Toolbar.Divider />
      <IconButton aria-label="Zoom in">
        <Plus />
      </IconButton>
    </Toolbar>
  ),
};
