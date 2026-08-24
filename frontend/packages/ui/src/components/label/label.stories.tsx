import type { Meta, StoryObj } from "@storybook/react-vite";

import { Label } from "./label";

const meta: Meta<typeof Label> = {
  title: "Components/Label",
  component: Label,
};
export default meta;

type Story = StoryObj<typeof Label>;

export const Default: Story = {
  render: () => <Label>Email address</Label>,
};
