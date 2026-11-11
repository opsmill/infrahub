import type { Meta, StoryObj } from "@storybook/react-vite";
import { fn } from "storybook/test";

import { ExportMenu } from "./export-menu";

const meta: Meta<typeof ExportMenu> = {
  title: "Graph/ExportMenu",
  component: ExportMenu,
};
export default meta;

type Story = StoryObj<typeof ExportMenu>;

export const Default: Story = {
  args: {
    onExport: fn(),
  },
};
