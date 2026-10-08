// PROTO number-pool — pool actions menu, mirroring the object details one. Delete with the prototype.
import { Button, Menu, MenuItem, MenuSection, MenuTrigger, Popover } from "@infrahub/ui";
import {
  ChevronDownIcon,
  CodeIcon,
  FileCodeIcon,
  GroupIcon,
  ListChecksIcon,
  PencilLineIcon,
  Trash2Icon,
} from "lucide-react";
import React from "react";
import { toast } from "react-toastify";

import { CopyToClipboardMenuItem } from "@/shared/components/menu/copy-to-clipboard-menu-item";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import type { Dataset } from "./data";
import { EditPoolContext } from "./editor";

const notInProto = (what: string) => () =>
  toast(<Alert type={ALERT_TYPES.INFO} message={`${what} is outside this prototype.`} />);

export function PoolActionsMenu({ dataset }: { dataset: Dataset }) {
  const { pool } = dataset;
  const openEdit = React.useContext(EditPoolContext);
  const schemaLock = pool.schemaDefined
    ? `Defined by the schema attribute ${pool.targetKind}.${pool.targetAttribute}`
    : undefined;

  return (
    <MenuTrigger>
      <Button variant="outline" size="sm" className="shrink-0">
        Actions <ChevronDownIcon className="size-3.5" />
      </Button>
      <Popover placement="bottom end">
        <Menu>
          <MenuSection title="Actions">
            <CopyToClipboardMenuItem textToCopy={pool.id}>Copy ID</CopyToClipboardMenuItem>
            <CopyToClipboardMenuItem textToCopy={pool.name}>Copy HFID</CopyToClipboardMenuItem>
          </MenuSection>
          <MenuSection title="Go to">
            <MenuItem onAction={notInProto("Tasks")}>
              <ListChecksIcon />
              Tasks
            </MenuItem>
            {pool.schemaDefined && (
              <MenuItem href="/schema?kind=InfraAutonomousSystem">
                <FileCodeIcon />
                Schema attribute
              </MenuItem>
            )}
            <MenuItem onAction={notInProto("GraphQL sandbox")}>
              <CodeIcon />
              GraphQL sandbox
            </MenuItem>
          </MenuSection>
          <MenuSection title="Manage">
            <MenuItem
              isDisabled={pool.schemaDefined}
              tooltip={schemaLock}
              onAction={openEdit ?? notInProto("The range editor")}
            >
              <PencilLineIcon />
              <span>Edit</span>
            </MenuItem>
            <MenuItem onAction={notInProto("Groups")}>
              <GroupIcon />
              <span>Groups</span>
            </MenuItem>
            <MenuItem
              isDisabled={pool.schemaDefined}
              tooltip={schemaLock}
              className="text-danger"
              onAction={notInProto("Delete")}
            >
              <Trash2Icon />
              <span>Delete</span>
            </MenuItem>
          </MenuSection>
        </Menu>
      </Popover>
    </MenuTrigger>
  );
}
