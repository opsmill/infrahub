import type { Meta, StoryObj } from "@storybook/react-vite";

import { Button } from "../button/button";
import { Popover, PopoverDialog, type PopoverProps, PopoverTrigger } from "./popover";

const WIDTHS = ["trigger", "min-trigger", "content"] as const satisfies readonly NonNullable<
  PopoverProps["width"]
>[];

const CONTENTS = {
  short: "Short.",
  long: "Content that needs more room than the trigger it hangs from.",
};

const meta: Meta<typeof Popover> = {
  title: "Components/Popover",
  component: Popover,
  parameters: {
    layout: "centered",
  },
};
export default meta;

type Story = StoryObj<typeof meta>;

export const AllVariants: Story = {
  render: () => (
    <div className="flex flex-col gap-4">
      {WIDTHS.map((width) => (
        <div key={width} className="flex flex-col gap-1">
          <div className="font-medium text-subtle-muted text-xxs uppercase tracking-wider">
            {width}
          </div>

          <div className="flex gap-2">
            {Object.entries(CONTENTS).map(([label, content]) => (
              <PopoverTrigger key={label}>
                <Button variant="outline" className="w-64">
                  {label} content
                </Button>
                <Popover width={width}>
                  <PopoverDialog className="p-4">
                    <p className="text-sm">{content}</p>
                  </PopoverDialog>
                </Popover>
              </PopoverTrigger>
            ))}
          </div>
        </div>
      ))}
    </div>
  ),
};
