import { GroupsManager } from "@/entities/groups/ui/groups-manager";
import ObjectItemEditComponent from "@/entities/nodes/object-item-edit/object-item-edit-paginated";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { NodeObject } from "@/entities/nodes/types";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { Permission } from "@/entities/permission/types";
import { ModelSchema } from "@/entities/schema/types";
import { queryClient } from "@/shared/api/rest/client";
import { constructPath } from "@/shared/api/rest/fetch";
import {
  CopyToClipboardMenuItem,
  Menu,
  MenuHeader,
  MenuItem,
  MenuPopover,
  MenuSection,
  MenuTrigger,
} from "@/shared/components/aria/menu";
import { Button, ButtonProps } from "@/shared/components/buttons/button-primitive";
import SlideOver, { SlideOverTitle } from "@/shared/components/display/slide-over";
import ModalDeleteObject from "@/shared/components/modals/modal-delete-object";
import { Icon } from "@iconify-icon/react";
import { jsonToGraphQLQuery } from "json-to-graphql-query";
import { GroupIcon, PencilLineIcon, Trash2Icon } from "lucide-react";
import { useState } from "react";
import { Pressable } from "react-aria-components";
import { useNavigate } from "react-router";

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
          <Button variant="ghost" size="xs" className="p-4 shrink-0" {...props}>
            <Icon icon="mdi:dots-vertical" />
          </Button>
        </Pressable>

        <MenuPopover placement="bottom end">
          <Menu>
            <MenuSection>
              <MenuHeader>Actions</MenuHeader>
              <CopyToClipboardMenuItem textToCopy={objectData.id}>Copy ID</CopyToClipboardMenuItem>
              {objectData.hfid && (
                <CopyToClipboardMenuItem textToCopy={objectData.hfid.toString()}>
                  Copy HFID
                </CopyToClipboardMenuItem>
              )}
            </MenuSection>

            <MenuSection>
              <MenuHeader>Explore</MenuHeader>
              <MenuItem
                href={constructPath("/schema", [{ name: "kind", value: objectSchema.kind }])}
              >
                View schema
              </MenuItem>
              <MenuItem
                href={constructPath("/graphql", [
                  {
                    name: "query",
                    value: jsonToGraphQLQuery(
                      {
                        query: {
                          [objectSchema.kind as string]: {
                            edges: {
                              node: {
                                id: true,
                                hfid: true,
                              },
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
                GraphQL sandbox
              </MenuItem>
              {objectSchema.documentation && (
                <MenuItem href={objectSchema.documentation}>Documentation</MenuItem>
              )}
            </MenuSection>

            <MenuSection>
              <MenuHeader>Manage</MenuHeader>
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
          className="p-4 overflow-auto"
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
            await queryClient.invalidateQueries({
              predicate: (query) => query.queryKey.includes("objects"),
            });
          }}
          objectid={objectData.id!}
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
            return getObjectDetailsUrl(
              objectData.parent.node.__typename,
              objectData.parent.node.id
            );
          }

          navigate(getObjectDetailsUrl(objectSchema.kind as string, objectData.id));
        }}
      />
    </>
  );
}
