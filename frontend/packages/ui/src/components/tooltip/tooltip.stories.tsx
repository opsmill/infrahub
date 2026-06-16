import type { Meta, StoryObj } from "@storybook/react-vite";

import { Button } from "../button/button";
import { Tooltip } from "./tooltip";

const meta: Meta<typeof Tooltip> = {
  title: "Components/Tooltip",
  component: Tooltip,
};
export default meta;

type Story = StoryObj<typeof Tooltip>;

export const Default: Story = {
  args: {
    message: "Helpful hint",
    children: <Button>Hover me</Button>,
  },
};
