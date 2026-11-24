import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";

import { Button } from "../button/button";
import { Modal } from "./modal";

const meta: Meta<typeof Modal> = {
  component: Modal,
  parameters: {
    layout: "centered",
  },
  args: {
    isOpen: true,
    "aria-label": "Example modal",
  },
  argTypes: {
    isOpen: { control: "boolean" },
  },
};

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {
  render: (args) => (
    <Modal {...args}>
      <div className="flex flex-col gap-3 p-3">
        <h2 className="font-medium text-base text-foreground">Confirm action</h2>
        <p className="text-foreground-muted text-sm">
          This is a typical modal body. It can contain any content.
        </p>
        <div className="flex justify-end gap-2">
          <Button variant="outline">Cancel</Button>
          <Button>Confirm</Button>
        </div>
      </div>
    </Modal>
  ),
};

const ROOT_DEPTH = 0;
const NEXT_LEVEL = 1;

function NestedModal({ depth = ROOT_DEPTH }: { depth?: number }) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <Button onPress={() => setIsOpen(true)}>Open another</Button>
      <Modal
        isOpen={isOpen}
        onOpenChange={setIsOpen}
        aria-label={`Modal level ${depth + NEXT_LEVEL}`}
      >
        <div className="flex flex-col gap-3 p-3">
          <p className="text-foreground-muted text-sm">Level {depth + NEXT_LEVEL}</p>
          <NestedModal depth={depth + NEXT_LEVEL} />
        </div>
      </Modal>
    </>
  );
}

export const InfiniteNested: Story = {
  args: {},
  argTypes: {},
  render: () => <NestedModal />,
};
