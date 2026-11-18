import type { Meta, StoryObj } from "@storybook/react-vite";
import { use, useEffect, useState } from "react";

import { DismissGuardContext } from "../../hooks/use-dissmiss-guard";
import { Button } from "../button/button";
import { Sheet } from "./sheet";

const meta: Meta<typeof Sheet> = {
  component: Sheet,
  parameters: {
    layout: "centered",
  },
};

export default meta;

type Story = StoryObj<typeof meta>;

const ROOT_DEPTH = 0;
const NEXT_LEVEL = 1;

function NestedSheet({ depth = ROOT_DEPTH }: { depth?: number }) {
  const [isOpen, setIsOpen] = useState(false);
  const level = depth + NEXT_LEVEL;

  return (
    <>
      <Button onPress={() => setIsOpen(true)}>
        {depth === ROOT_DEPTH ? "Open sheet" : "Open another"}
      </Button>
      <Sheet isOpen={isOpen} onOpenChange={setIsOpen} aria-label={`Sheet level ${level}`}>
        <div className="flex flex-col gap-3">
          <h2 className="font-medium text-base text-foreground">Level {level}</h2>
          <p className="text-foreground-muted text-sm">
            Each open sheet pushes the previous ones to the left. Press Escape or click outside to
            close the topmost sheet.
          </p>
          <div className="flex gap-2">
            <NestedSheet depth={level} />
            <Button variant="outline" onPress={() => setIsOpen(false)}>
              Close
            </Button>
          </div>
        </div>
      </Sheet>
    </>
  );
}

export const Default: Story = {
  render: () => <NestedSheet />,
};

function DismissGuardContent({ close }: { close: () => void }) {
  const guard = use(DismissGuardContext);
  const [draft, setDraft] = useState("");
  const [showWarning, setShowWarning] = useState(false);
  const isDirty = draft !== "";

  useEffect(() => {
    if (!guard) {
      return;
    }
    guard.setDismissable(!isDirty, () => setShowWarning(true));
  }, [guard, isDirty]);

  return (
    <div className="flex flex-col gap-3">
      <h2 className="font-medium text-base text-foreground">Edit description</h2>
      <p className="text-foreground-muted text-sm">
        Type something below, then press Escape or click outside: the sheet refuses to close while
        the text is unsaved. Clear the text to make it dismissable again.
      </p>
      <textarea
        aria-label="Description"
        className="h-24 resize-none rounded-lg border border-border-strong p-2 text-sm outline-hidden focus:border-ring"
        placeholder="Unsaved changes block dismissal…"
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
      />
      {showWarning && isDirty && (
        <p className="text-red-600 text-sm" role="alert">
          Unsaved changes — save or discard them first.
        </p>
      )}
      <div className="flex justify-end gap-2">
        <Button variant="outline" onPress={close}>
          Discard
        </Button>
        <Button onPress={close}>Save</Button>
      </div>
    </div>
  );
}

function DismissGuardSheet() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <Button onPress={() => setIsOpen(true)}>Open sheet</Button>
      <Sheet isOpen={isOpen} onOpenChange={setIsOpen} aria-label="Dismiss guard example">
        <DismissGuardContent close={() => setIsOpen(false)} />
      </Sheet>
    </>
  );
}

export const DismissGuard: Story = {
  render: () => <DismissGuardSheet />,
};

export const Playground: Story = {
  args: {
    isOpen: true,
    "aria-label": "Playground sheet",
  },
  argTypes: {
    isOpen: { control: "boolean" },
  },
  render: (args) => (
    <Sheet {...args}>
      <div className="flex flex-col gap-3">
        <h2 className="font-medium text-base text-foreground">Sheet</h2>
        <p className="text-foreground-muted text-sm">
          A side panel anchored to the right edge of the viewport. Toggle the isOpen control to open
          and close it.
        </p>
      </div>
    </Sheet>
  ),
};
