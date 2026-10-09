import { Button, Menu, MenuItem, MenuSection, MenuTrigger, Popover, Sheet } from "@infrahub/ui";
import { BookTextIcon, ChevronDownIcon, GroupIcon, PencilLineIcon, Trash2Icon } from "lucide-react";
import React from "react";
import { useNavigate } from "react-router";

import TasksStatusIcon from "@/assets/icons/tasks-status.svg?react";

import { queryClient } from "@/shared/api/rest/client";
import { constructPath } from "@/shared/api/rest/fetch";
import { Icon } from "@/shared/components/display/icon";
import { SlideOverTitle } from "@/shared/components/display/slide-over";
import { CopyToClipboardMenuItem } from "@/shared/components/menu/copy-to-clipboard-menu-item";

import { GroupsManager } from "@/entities/groups/ui/groups-manager";
import ModalDeleteObject from "@/entities/nodes/object/ui/modal-delete-object";
import ObjectEdit from "@/entities/nodes/object/ui/object-edit/object-item-edit-paginated";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import {
  getDocumentationUrl,
  getObjectDetailsUrl,
  getObjectGraphqlSandboxUrl,
  getObjectTasksUrl,
} from "@/entities/nodes/object/ui/routing/object-urls";
import type { Permission, PermissionDecision } from "@/entities/permission/domain/model/permission";
import type { NumberPoolData } from "@/entities/resource-manager/domain/model/number-pool";
import {
  NUMBER_POOL_KIND,
  NUMBER_POOL_TYPE_SCHEMA,
} from "@/entities/resource-manager/domain/model/pool";
import { resourceManagerQueryKeys } from "@/entities/resource-manager/ui/queries/resource-manager.query-keys";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

export interface NumberPoolActionsMenuProps {
  pool: NumberPoolData;
  schema: ModelSchema;
  permission: Permission;
}

export function NumberPoolActionsMenu({ pool, schema, permission }: NumberPoolActionsMenuProps) {
  const [isGroupsOpen, setIsGroupsOpen] = React.useState(false);
  const [isEditOpen, setIsEditOpen] = React.useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = React.useState(false);
  const navigate = useNavigate();

  const isSchemaManaged = pool.pool_type.value === NUMBER_POOL_TYPE_SCHEMA;
  const schemaLock: PermissionDecision = {
    isAllowed: false,
    message: `Defined by the schema attribute ${pool.node.value}.${pool.node_attribute.value}`,
  };
  const updateDecision = isSchemaManaged ? schemaLock : permission.update;
  const deleteDecision = isSchemaManaged ? schemaLock : permission.delete;

  return (
    <>
      <MenuTrigger>
        <Button variant="outline" size="sm" className="shrink-0">
          Actions <ChevronDownIcon className="size-3.5" />
        </Button>

        <Popover placement="bottom end">
          <Menu>
            <MenuSection title="Actions">
              <CopyToClipboardMenuItem textToCopy={pool.id}>Copy ID</CopyToClipboardMenuItem>
              {pool.hfid && (
                <CopyToClipboardMenuItem textToCopy={pool.hfid.toString()}>
                  Copy HFID
                </CopyToClipboardMenuItem>
              )}
            </MenuSection>

            <MenuSection title="Go to">
              <MenuItem href={getObjectTasksUrl(pool.id)}>
                <TasksStatusIcon width="12" height="12" className="ml-0.5" />
                Tasks
              </MenuItem>
              <MenuItem
                href={constructPath("/schema", [{ name: "kind", value: NUMBER_POOL_KIND }])}
              >
                <Icon icon="mdi:code-json" />
                View schema
              </MenuItem>
              <MenuItem href={getObjectGraphqlSandboxUrl(NUMBER_POOL_KIND, pool.id)}>
                <Icon icon="mdi:graphql" />
                GraphQL sandbox
              </MenuItem>
              {schema.documentation && (
                <MenuItem
                  href={getDocumentationUrl(schema.documentation)}
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
                onAction={() => setIsEditOpen(true)}
              >
                <PencilLineIcon />
                <span>Edit</span>
              </MenuItem>
              <MenuItem
                isDisabled={!updateDecision.isAllowed}
                tooltip={updateDecision.message}
                onAction={() => setIsGroupsOpen(true)}
              >
                <GroupIcon />
                <span>Groups</span>
              </MenuItem>
              <MenuItem
                isDisabled={!deleteDecision.isAllowed}
                tooltip={deleteDecision.message}
                className="text-danger"
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
          objectKind={NUMBER_POOL_KIND}
        />
      </Sheet>

      <ModalDeleteObject
        label={schema.label}
        rowToDelete={pool}
        isOpen={isDeleteOpen}
        onOpenChange={setIsDeleteOpen}
        onDelete={() => navigate(getObjectDetailsUrl(NUMBER_POOL_KIND))}
      />
    </>
  );
}
