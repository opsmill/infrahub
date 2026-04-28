import type { Meta, StoryObj } from "@storybook/react-vite";

import { PencilIcon } from "lucide-react";

import { Button, type ButtonProps, buttonVariants } from "./button";

const VARIANTS = Object.keys(buttonVariants.variants.variant) as ButtonProps["variant"][];
const SIZES = Object.keys(buttonVariants.variants.size) as ButtonProps["size"][];

const ICON_SIZES = new Set(["icon", "square"]) as Set<ButtonProps["size"]>;

function buttonContent(size: ButtonProps["size"]) {
  if (ICON_SIZES.has(size)) {
    return <PencilIcon size={14} />;
  }
  return size;
}

const meta: Meta<typeof Button> = {
  component: Button,
  parameters: {
    layout: "centered",
  },
  args: {
    disabled: false,
  },
  argTypes: {
    variant: { control: "select", options: VARIANTS },
    size: { control: "select", options: SIZES },
    disabled: { control: "boolean" },
    ref: { table: { disable: true } },
    type: { table: { disable: true } },
  },
};

export default meta;

type Story = StoryObj<typeof meta>;

export const AllVariants: Story = {
  argTypes: {
    variant: { table: { disable: true } },
    size: { table: { disable: true } },
    children: { table: { disable: true } },
  },
  render: ({ disabled }) => (
    <div className="flex flex-col gap-4">
      {VARIANTS.map((variant) => (
        <div key={variant} className="flex items-center gap-2">
          <span className="w-30 text-xs text-gray-500">{variant}</span>
          {SIZES.map((size) => (
            <Button key={`${variant}-${size}`} variant={variant} size={size} disabled={disabled}>
              {buttonContent(size)}
            </Button>
          ))}
        </div>
      ))}
    </div>
  ),
  parameters: {
    layout: "padded",
  },
};

export const Playground: Story = {
  args: {
    children: "Button",
  },
};
