import type { Meta, StoryObj } from "@storybook/react-vite";
import { Plus } from "lucide-react";

import { IconButton } from "./icon-button";

const meta: Meta<typeof IconButton> = {
  title: "Components/IconButton",
  component: IconButton,
};
export default meta;

type Story = StoryObj<typeof IconButton>;

export const Default: Story = {
  args: { "aria-label": "Add", children: <Plus /> },
};
