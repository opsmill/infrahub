import type { Meta, StoryObj } from "@storybook/react-vite";
import { PencilIcon, PlusIcon } from "lucide-react";
import type React from "react";

import { Button, type ButtonProps, buttonVariants } from "./button";

const VARIANTS = Object.keys(buttonVariants.variants.variant) as ButtonProps["variant"][];
const SIZES = Object.keys(buttonVariants.variants.size) as ButtonProps["size"][];
const SHAPES = Object.keys(buttonVariants.variants.shape) as ButtonProps["shape"][];

const meta: Meta<typeof Button> = {
  component: Button,
  parameters: {
    layout: "centered",
  },
  args: {
    isDisabled: false,
  },
  argTypes: {
    variant: { control: "select", options: VARIANTS },
    size: { control: "select", options: SIZES },
    shape: { control: "select", options: SHAPES },
    isDisabled: { control: "boolean" },
    isPending: { control: "boolean" },
  },
};

export default meta;

type Story = StoryObj<typeof meta>;

function ColumnLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="font-medium text-[10px] text-subtle-muted uppercase tracking-wider">
      {children}
    </div>
  );
}

function Divider() {
  return <div className="h-9 w-px self-center bg-border" />;
}

export const AllVariants: Story = {
  argTypes: {
    variant: { table: { disable: true } },
    size: { table: { disable: true } },
    shape: { table: { disable: true } },
    children: { table: { disable: true } },
  },
  render: ({ isDisabled }) => {
    const renderRow = (
      label: string,
      variant: ButtonProps["variant"],
      rowProps: Partial<ButtonProps> = {}
    ) => (
      <div key={label} className="contents">
        <div className="font-medium text-sm text-subtle">{label}</div>

        <div className="flex flex-wrap items-center gap-2">
          {SIZES.map((size) => (
            <Button key={`${label}-${size}-text`} variant={variant} size={size} {...rowProps}>
              <PencilIcon className="h-3.5 w-3.5" />
              {size}
            </Button>
          ))}
        </div>

        <Divider />

        <div className="flex flex-wrap items-center gap-2">
          {SIZES.map((size) => (
            <Button
              key={`${label}-${size}-square`}
              variant={variant}
              size={size}
              shape="square"
              aria-label={`${label} ${size} square`}
              {...rowProps}
            >
              <PlusIcon className="h-3.5 w-3.5" />
            </Button>
          ))}
        </div>

        <Divider />

        <div className="flex flex-wrap items-center gap-2">
          {SIZES.map((size) => (
            <Button
              key={`${label}-${size}-circle`}
              variant={variant}
              size={size}
              shape="circle"
              aria-label={`${label} ${size} circle`}
              {...rowProps}
            >
              <PlusIcon className="h-3.5 w-3.5" />
            </Button>
          ))}
        </div>
      </div>
    );

    return (
      <div className="grid min-w-fit grid-cols-[8rem_auto_1px_auto_1px_auto] items-center gap-x-4 gap-y-3">
        <div />
        <ColumnLabel>Text + icon</ColumnLabel>
        <div />
        <ColumnLabel>Square</ColumnLabel>
        <div />
        <ColumnLabel>Circle</ColumnLabel>

        {VARIANTS.map((variant) => renderRow(variant ?? "primary", variant, { isDisabled }))}

        {renderRow("disabled", "primary", { isDisabled: true })}
        {renderRow("pending", "primary", { isPending: true })}
      </div>
    );
  },
  parameters: {
    layout: "padded",
  },
};

export const Playground: Story = {
  args: {
    variant: "primary",
    size: "md",
    shape: "default",
    children: "Button",
  },
};
