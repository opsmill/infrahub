import type { Meta, StoryObj } from "@storybook/react-vite";
import type React from "react";

import { CopyIcon, GroupIcon, PencilLineIcon, Trash2Icon } from "lucide-react";

import { Menu, MenuItem, MenuSection } from "./menu";

const meta: Meta<typeof Menu> = {
  title: "Components/Menu",
  component: Menu,
  parameters: {
    layout: "centered",
  },
};

export default meta;

type Story = StoryObj<typeof meta>;

const ColumnLabel = ({ children }: { children: React.ReactNode }) => (
  <div className="font-medium text-[10px] text-neutral-400 uppercase tracking-wider">
    {children}
  </div>
);

// The menu lives inside a Popover in real usage; this mimics that surface so the  items render against the expected background.
const MenuSurface = ({ children }: { children: React.ReactNode }) => (
  <div className="w-56 rounded-xl border border-neutral-300 bg-stone-100/70 shadow-md">
    {children}
  </div>
);

export const Default: Story = {
  render: () => (
    <div className="grid grid-cols-[8rem_auto]  items-start gap-x-6 gap-y-6">
      <ColumnLabel>Simple</ColumnLabel>
      <MenuSurface>
        <Menu aria-label="Simple menu">
          <MenuItem>
            <PencilLineIcon className="size-3.5" />
            <span>Edit</span>
          </MenuItem>
          <MenuItem>
            <CopyIcon className="size-3.5" />
            <span>Duplicate</span>
          </MenuItem>
          <MenuItem className="text-red-500">
            <Trash2Icon className="size-3.5" />
            <span>Delete</span>
          </MenuItem>
        </Menu>
      </MenuSurface>

      <ColumnLabel>With sections</ColumnLabel>
      <MenuSurface>
        <Menu aria-label="Menu with sections">
          <MenuSection title="Actions">
            <MenuItem>Copy ID</MenuItem>
            <MenuItem>Copy HFID</MenuItem>
          </MenuSection>
          <MenuSection title="Manage">
            <MenuItem>
              <PencilLineIcon className="size-3.5" />
              <span>Edit</span>
            </MenuItem>
            <MenuItem>
              <GroupIcon className="size-3.5" />
              <span>Groups</span>
            </MenuItem>
          </MenuSection>
        </Menu>
      </MenuSurface>

      <ColumnLabel>Disabled + tooltip</ColumnLabel>
      <div className="space-y-1">
        <MenuSurface>
          <Menu aria-label="Menu with a disabled item">
            <MenuItem>
              <PencilLineIcon className="size-3.5" />
              <span>Edit</span>
            </MenuItem>
            <MenuItem
              isDisabled
              tooltip="You don't have permission to delete this object"
              className="text-red-500"
            >
              <Trash2Icon className="size-3.5" />
              <span>Delete</span>
            </MenuItem>
          </Menu>
        </MenuSurface>
        <p className="text-[10px] text-neutral-400">Hover the disabled item to see the tooltip.</p>
      </div>
    </div>
  ),
  parameters: {
    layout: "padded",
  },
};
