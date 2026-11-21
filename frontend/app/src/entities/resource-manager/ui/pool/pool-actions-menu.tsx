import { Button, Menu, MenuItem, MenuSection, MenuTrigger, Popover, Sheet } from "@infrahub/ui";
import { BookTextIcon, ChevronDownIcon, GroupIcon, PencilLineIcon, Trash2Icon } from "lucide-react";
import React from "react";

import TasksStatusIcon from "@/assets/icons/tasks-status.svg?react";

import { queryClient } from "@/shared/api/rest/client";
import { constructPath } from "@/shared/api/rest/fetch";
import { Icon } from "@/shared/components/display/icon";
import { SlideOverTitle } from "@/shared/components/display/slide-over";
import { CopyToClipboardMenuItem } from "@/shared/components/menu/copy-to-clipboard-menu-item";

import { GroupsManager } from "@/entities/groups/ui/groups-manager";
import type { NodeAttribute, NodeCore } from "@/entities/nodes/object/domain/model/node";
import ModalDeleteObject from "@/entities/nodes/object/ui/modal-delete-object";
import ObjectEdit from "@/entities/nodes/object/ui/object-edit/object-item-edit-paginated";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import {
  getDocumentationUrl,
  getObjectGraphqlSandboxUrl,
  getObjectTasksUrl,
} from "@/entities/nodes/object/ui/routing/object-urls";
import type { PermissionDecision } from "@/entities/permission/domain/model/permission";
import { resourceManagerQueryKeys } from "@/entities/resource-manager/ui/queries/resource-manager.query-keys";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

export interface PoolActionsMenuProps {
  pool: NodeCore & { name: NodeAttribute<string> };
  poolKind: string;
  schema: ModelSchema;
  updateDecision: PermissionDecision;
  deleteDecision: PermissionDecision;
  onDeleted: () => void;
}

export function PoolActionsMenu({
  pool,
  poolKind,
  schema,
  updateDecision,
  deleteDecision,
  onDeleted,
}: PoolActionsMenuProps) {
  const [isGroupsOpen, setIsGroupsOpen] = React.useState(false);
  const [isEditOpen, setIsEditOpen] = React.useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = React.useState(false);

  return (
    <>
      <MenuTrigger>
        <Button variant="outline" size="sm" className="shrink-0">
          Actions <ChevronDownIcon className="size-3.5" />
        </Button>

        <Popover placement="bottom end">
          <Menu>
            <MenuSection title="Actions">
              <CopyToClipboardMenuItem textToCopy={pool.id} textValue="Copy ID">
                Copy ID
              </CopyToClipboardMenuItem>
              {pool.hfid && (
                <CopyToClipboardMenuItem textToCopy={pool.hfid.toString()} textValue="Copy HFID">
                  Copy HFID
                </CopyToClipboardMenuItem>
              )}
            </MenuSection>

            <MenuSection title="Go to">
              <MenuItem href={getObjectTasksUrl(pool.id)} textValue="Tasks">
                <TasksStatusIcon width="12" height="12" className="ml-0.5" />
                Tasks
              </MenuItem>
              <MenuItem
                href={constructPath("/schema", [{ name: "kind", value: poolKind }])}
                textValue="View schema"
              >
                <Icon icon="mdi:code-json" />
                View schema
              </MenuItem>
              <MenuItem
                href={getObjectGraphqlSandboxUrl(poolKind, pool.id)}
                textValue="GraphQL sandbox"
              >
                <Icon icon="mdi:graphql" />
                GraphQL sandbox
              </MenuItem>
              {schema.documentation && (
                <MenuItem
                  href={getDocumentationUrl(schema.documentation)}
                  textValue="Documentation"
                  target="_blank"
                  rel="noreferrer"
                >
                  <BookTextIcon />
                  Documentation
                </MenuItem>
              )}
            </MenuSection>

            <MenuSection title="Manage">
              <MenuItem
                isDisabled={!updateDecision.isAllowed}
                tooltip={updateDecision.message}
                textValue="Edit"
                onAction={() => setIsEditOpen(true)}
              >
                <PencilLineIcon />
                <span>Edit</span>
              </MenuItem>
              <MenuItem
                isDisabled={!updateDecision.isAllowed}
                tooltip={updateDecision.message}
                textValue="Groups"
                onAction={() => setIsGroupsOpen(true)}
              >
                <GroupIcon />
                <span>Groups</span>
              </MenuItem>
              <MenuItem
                isDisabled={!deleteDecision.isAllowed}
                tooltip={deleteDecision.message}
                className="text-danger"
                textValue="Delete"
                onAction={() => setIsDeleteOpen(true)}
              >
                <Trash2Icon />
                <span>Delete</span>
              </MenuItem>
            </MenuSection>
          </Menu>
        </Popover>
      </MenuTrigger>

      <Sheet isOpen={isGroupsOpen} onOpenChange={setIsGroupsOpen}>
        <SlideOverTitle
          schema={schema}
          currentObjectLabel={pool.name.value}
          title="Manage groups"
          subtitle="Add and unassign groups"
        />
        <GroupsManager schema={schema} objectId={pool.id} />
      </Sheet>

      <Sheet isOpen={isEditOpen} onOpenChange={setIsEditOpen}>
        <SlideOverTitle
          schema={schema}
          currentObjectLabel={pool.name.value}
          title={`Edit ${pool.name.value}`}
          subtitle={schema.description}
        />
        <ObjectEdit
          closeDrawer={() => setIsEditOpen(false)}
          onUpdateComplete={async () => {
            await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
            await queryClient.invalidateQueries({ queryKey: resourceManagerQueryKeys.all });
            setIsEditOpen(false);
          }}
          objectId={pool.id}
          objectKind={poolKind}
        />
      </Sheet>

      <ModalDeleteObject
        label={schema.label}
        rowToDelete={pool}
        isOpen={isDeleteOpen}
        onOpenChange={setIsDeleteOpen}
        onDelete={onDeleted}
      />
    </>
  );
}
