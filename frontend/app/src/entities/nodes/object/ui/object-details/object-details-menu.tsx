import { Icon } from "@iconify-icon/react";
import { jsonToGraphQLQuery } from "json-to-graphql-query";
import { BookTextIcon, GroupIcon, PencilLineIcon, Trash2Icon } from "lucide-react";
import { useState } from "react";
import { Pressable } from "react-aria-components";
import { useNavigate } from "react-router";

import TasksStatusIcon from "@/assets/icons/tasks-status.svg?react";

import { nodeCoreFragment } from "@/shared/api/graphql/fragments";
import { queryClient } from "@/shared/api/rest/client";
import { constructPath } from "@/shared/api/rest/fetch";
import {
  CopyToClipboardMenuItem,
  Menu,
  MenuItem,
  MenuPopover,
  MenuSection,
  MenuTrigger,
} from "@/shared/components/aria/menu";
import { Button, type ButtonProps } from "@/shared/components/buttons/button-primitive";
import SlideOver, { SlideOverTitle } from "@/shared/components/display/slide-over";
import ModalDeleteObject from "@/shared/components/modals/modal-delete-object";
import { INFRAHUB_DOC_LOCAL } from "@/shared/config/config";
import { QSP } from "@/shared/config/qsp";

import { GroupsManager } from "@/entities/groups/ui/groups-manager";
import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import ObjectItemEditComponent from "@/entities/nodes/object-item-edit/object-item-edit-paginated";
import type { NodeObject } from "@/entities/nodes/types";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import type { Permission } from "@/entities/permission/types";
import type { ModelSchema } from "@/entities/schema/types";

export interface ObjectDetailsMenuProps extends ButtonProps {
  objectSchema: ModelSchema;
  objectData: NodeObject;
  permission: Permission;
}

export function ObjectDetailsMenu({
  objectSchema,
  objectData,
  permission,
  ...props
}: ObjectDetailsMenuProps) {
  const [isManageGroupsDrawerOpen, setIsManageGroupsDrawerOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const navigate = useNavigate();

  const nodeLabel = getNodeLabel(objectData);

  const isEditAllowed = permission.update.isAllowed;
  const isDeleteAllowed = permission.delete.isAllowed;

  return (
    <>
      <MenuTrigger>
        <Pressable>
          <Button
            variant="ghost"
            className="size-7 shrink-0 p-0"
            data-testid="object-details-menu"
            {...props}
          >
            <Icon icon="mdi:dots-vertical" />
          </Button>
        </Pressable>

        <MenuPopover>
          <Menu>
            <MenuSection title="Actions">
              <CopyToClipboardMenuItem textToCopy={objectData.id}>Copy ID</CopyToClipboardMenuItem>
              {objectData.hfid && (
                <CopyToClipboardMenuItem textToCopy={objectData.hfid.toString()}>
                  Copy HFID
                </CopyToClipboardMenuItem>
              )}
            </MenuSection>

            <MenuSection title="Go to">
              <MenuItem
                href={constructPath(
                  `/tasks?${QSP.FILTER}=[{"name":"node__value","value":"${objectData.id}"}]`
                )}
              >
                <TasksStatusIcon width="12" height="12" className="ml-0.5" />
                Tasks
              </MenuItem>
              <MenuItem
                href={constructPath("/schema", [{ name: "kind", value: objectSchema.kind }])}
              >
                <Icon icon="mdi:code-json" />
                View schema
              </MenuItem>
              <MenuItem
                href={constructPath("/graphql", [
                  {
                    name: "query",
                    value: jsonToGraphQLQuery(
                      {
                        query: {
                          [objectData.__typename]: {
                            __args: {
                              ids: [objectData.id],
                            },
                            edges: {
                              node: nodeCoreFragment,
                            },
                          },
                        },
                      },
                      {
                        pretty: true,
                      }
                    ),
                  },
                ])}
              >
                <Icon icon="mdi:graphql" />
                GraphQL sandbox
              </MenuItem>
              {objectSchema.documentation && (
                <MenuItem
                  href={
                    objectSchema.documentation.startsWith("http")
                      ? objectSchema.documentation
                      : `${INFRAHUB_DOC_LOCAL}${objectSchema.documentation}`
                  }
                  target="_blank"
                  rel="noreferrer"
                >
                  <BookTextIcon className="size-3.5" />
                  Documentation
                </MenuItem>
              )}
            </MenuSection>

            <MenuSection title="Manage">
              <MenuItem isDisabled={!isEditAllowed} onAction={() => setIsEditModalOpen(true)}>
                <PencilLineIcon className="size-3.5" />
                <span>Edit</span>
              </MenuItem>

              <MenuItem
                isDisabled={!isEditAllowed}
                onAction={() => setIsManageGroupsDrawerOpen(true)}
              >
                <GroupIcon className="size-3.5" />
                <span>Groups</span>
              </MenuItem>

              <MenuItem
                href={constructPath(`/objects/${objectData.__typename}/${objectData.id}/convert`)}
                isDisabled={!isEditAllowed}
              >
                <Icon icon="mdi:swap-horizontal" className="size-3" />
                Convert object type
              </MenuItem>

              <MenuItem
                isDisabled={!isDeleteAllowed}
                className="text-red-500"
                onAction={() => setIsDeleteModalOpen(true)}
              >
                <Trash2Icon className="size-3.5" />
                <span>Delete</span>
              </MenuItem>
            </MenuSection>
          </Menu>
        </MenuPopover>
      </MenuTrigger>

      <SlideOver
        open={isManageGroupsDrawerOpen}
        setOpen={setIsManageGroupsDrawerOpen}
        title={
          <SlideOverTitle
            schema={objectSchema}
            currentObjectLabel={nodeLabel}
            title="Manage groups"
            subtitle="Add and unassign groups"
          />
        }
      >
        <GroupsManager
          schema={objectSchema}
          objectId={objectData.id}
          className="overflow-auto p-4"
        />
      </SlideOver>

      <SlideOver
        title={
          <SlideOverTitle
            schema={objectSchema}
            currentObjectLabel={nodeLabel}
            title={`Edit ${nodeLabel}`}
            subtitle={objectSchema.description}
          />
        }
        open={isEditModalOpen}
        setOpen={setIsEditModalOpen}
      >
        <ObjectItemEditComponent
          closeDrawer={() => setIsEditModalOpen(false)}
          onUpdateComplete={async () => {
            await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
            setIsEditModalOpen(false);
          }}
          objectId={objectData.id!}
          objectname={objectSchema.kind!}
        />
      </SlideOver>

      <ModalDeleteObject
        label={objectSchema.label}
        rowToDelete={objectData}
        open={isDeleteModalOpen}
        close={() => setIsDeleteModalOpen(false)}
        onDelete={() => {
          if ("parent" in objectData && "node" in objectData.parent && objectData.parent.node) {
            navigate(
              getObjectDetailsUrl(objectData.parent.node.__typename, objectData.parent.node.id)
            );
          } else {
            navigate(getObjectDetailsUrl(objectSchema.kind as string));
          }
        }}
      />
    </>
  );
}
