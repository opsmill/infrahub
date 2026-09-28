import type { Meta, StoryObj } from "@storybook/react-vite";
import { CopyIcon, GroupIcon, PencilLineIcon, Trash2Icon } from "lucide-react";
import React from "react";

import { Autocomplete } from "../autocomplete/autocomplete";
import { Button } from "../button/button";
import { Popover } from "../popover/popover";
import { Menu, MenuItem, MenuSection, MenuTrigger, SubmenuTrigger } from "./menu";

const meta: Meta<typeof Menu> = {
  title: "Components/Menu",
  component: Menu,
  parameters: {
    layout: "centered",
  },
};

export default meta;

type Story = StoryObj<typeof meta>;

function ColumnLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="font-medium text-subtle-muted text-xxs uppercase tracking-wider">
      {children}
    </div>
  );
}

// The menu lives inside a Popover in real usage; this mimics that surface so the  items render against the expected background.
function MenuSurface({ children }: { children: React.ReactNode }) {
  return (
    <div className="w-56 rounded-xl border border-border-strong bg-popover shadow-md backdrop-blur-lg">
      {children}
    </div>
  );
}

// Item sets shared across both variants, so each scenario renders identically as action and picker.
const simpleItems = () => [
  <MenuItem key="edit">
    <PencilLineIcon />
    <span>Edit</span>
  </MenuItem>,
  <MenuItem key="duplicate">
    <CopyIcon />
    <span>Duplicate</span>
  </MenuItem>,
  <MenuItem key="delete" className="text-red-500">
    <Trash2Icon />
    <span>Delete</span>
  </MenuItem>,
];

const sectionItems = () => [
  <MenuSection key="actions" title="Actions">
    <MenuItem>Copy ID</MenuItem>
    <MenuItem>Copy HFID</MenuItem>
  </MenuSection>,
  <MenuSection key="manage" title="Manage">
    <MenuItem>
      <PencilLineIcon />
      <span>Edit</span>
    </MenuItem>
    <MenuItem>
      <GroupIcon />
      <span>Groups</span>
    </MenuItem>
  </MenuSection>,
];

const disabledItems = () => [
  <MenuItem key="edit">
    <PencilLineIcon />
    <span>Edit</span>
  </MenuItem>,
  <MenuItem
    key="delete"
    isDisabled
    tooltip="You don't have permission to delete this object"
    className="text-red-500"
  >
    <Trash2Icon />
    <span>Delete</span>
  </MenuItem>,
];

export const AllVariants: Story = {
  render: () => (
    <div className="grid grid-cols-[8rem_max-content_max-content] items-start gap-x-6 gap-y-6">
      <div />
      <ColumnLabel>action (default)</ColumnLabel>
      <ColumnLabel>picker</ColumnLabel>

      <ColumnLabel>Simple</ColumnLabel>
      <MenuSurface>
        <Menu aria-label="Simple action menu" variant="action">
          {simpleItems()}
        </Menu>
      </MenuSurface>
      <MenuSurface>
        <Menu aria-label="Simple picker menu" variant="picker">
          {simpleItems()}
        </Menu>
      </MenuSurface>

      <ColumnLabel>With sections</ColumnLabel>
      <MenuSurface>
        <Menu aria-label="Action menu with sections" variant="action">
          {sectionItems()}
        </Menu>
      </MenuSurface>
      <MenuSurface>
        <Menu aria-label="Picker menu with sections" variant="picker">
          {sectionItems()}
        </Menu>
      </MenuSurface>

      <ColumnLabel>Disabled + tooltip</ColumnLabel>
      <div className="space-y-1">
        <MenuSurface>
          <Menu aria-label="Action menu with a disabled item" variant="action">
            {disabledItems()}
          </Menu>
        </MenuSurface>
        <p className="text-subtle-muted text-xxs">Hover the disabled item to see the tooltip.</p>
      </div>
      <MenuSurface>
        <Menu aria-label="Picker menu with a disabled item" variant="picker">
          {disabledItems()}
        </Menu>
      </MenuSurface>
    </div>
  ),
  parameters: {
    layout: "padded",
  },
};

/*
 * The picker pattern that drives AddSort: a filtered field list whose items each open an
 * asc/desc submenu. The submenu inherits variant="picker" from its parent — no prop needed.
 */
const SORT_FIELDS = ["Name", "Description", "Created at", "Site › Name", "Device › Role"];
const DIRECTIONS = [
  { id: "asc", label: "Ascending" },
  { id: "desc", label: "Descending" },
];

function PickerWithSubmenuRender() {
  const [picked, setPicked] = React.useState<string | null>(null);
  return (
    <div className="flex flex-col items-start gap-3">
      <MenuTrigger>
        <Button variant="outline" size="sm">
          Add sort
        </Button>
        <Popover placement="bottom start" className="w-56">
          <Autocomplete>
            <Menu
              variant="picker"
              aria-label="Sort field"
              className="max-h-72"
              emptyMessage="No fields match"
            >
              {SORT_FIELDS.map((field) => (
                <SubmenuTrigger key={field}>
                  <MenuItem textValue={field}>{field}</MenuItem>
                  <Popover>
                    <Menu
                      aria-label={`Direction for ${field}`}
                      onAction={(key) => setPicked(`${field} · ${key}`)}
                    >
                      {DIRECTIONS.map((d) => (
                        <MenuItem key={d.id} id={d.id} textValue={d.label}>
                          {d.label}
                        </MenuItem>
                      ))}
                    </Menu>
                  </Popover>
                </SubmenuTrigger>
              ))}
            </Menu>
          </Autocomplete>
        </Popover>
      </MenuTrigger>
      <p className="text-subtle-muted text-xs">Picked: {picked ?? "—"}</p>
    </div>
  );
}

export const PickerWithSubmenu: Story = {
  render: () => <PickerWithSubmenuRender />,
};
