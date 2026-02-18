import type { Meta, StoryObj } from "@storybook/react";

import { Badge, badgeVariants } from "./badge";

const meta: Meta<typeof Badge> = {
  title: "Badge",
  component: Badge,
  parameters: {
    layout: "centered",
  },
  args: {
    children: "badge",
  },
  argTypes: {
    variant: {
      control: "select",
      options: Object.keys(badgeVariants.variants.variant),
    },
  },
};

export default meta;

type Story = StoryObj<typeof meta>;

export const Green: Story = {
  args: {
    variant: "green",
  },
};
