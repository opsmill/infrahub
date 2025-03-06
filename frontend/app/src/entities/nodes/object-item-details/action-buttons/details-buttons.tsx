import { GENERIC_REPOSITORY_KIND } from "@/config/constants";
import { GroupsManagerTriggerButton } from "@/entities/groups/ui/groups-manager-trigger-button";
import ObjectItemEditComponent from "@/entities/nodes/object-item-edit/object-item-edit-paginated";
import { getObjectDetailsUrl2 } from "@/entities/nodes/utils";
import { Permission } from "@/entities/permission/types";
import RepositoryActionMenu from "@/entities/repository/ui/repository-action-menu";
import { ModelSchema } from "@/entities/schema/types";
import { isGenericSchema } from "@/entities/schema/utils/is-generic-schema";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { ButtonWithTooltip } from "@/shared/components/buttons/button-primitive";
import SlideOver, { SlideOverTitle } from "@/shared/components/display/slide-over";
import ModalDeleteObject from "@/shared/components/modals/modal-delete-object";
import { Icon } from "@iconify-icon/react";
import { useState } from "react";
import { useNavigate } from "react-router";

type DetailsButtonsProps = {
  schema: ModelSchema;
  objectDetailsData: any;
  permission: Permission;
};

export function DetailsButtons({ schema, objectDetailsData, permission }: DetailsButtonsProps) {
  const navigate = useNavigate();

  const [showEditModal, setShowEditModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);

  return (
    <>
      <div className="flex items-center gap-2">
        <ButtonWithTooltip
          disabled={!permission.update.isAllowed}
          tooltipEnabled
          tooltipContent={permission.update.message ?? "Edit object"}
          onClick={() => setShowEditModal(true)}
          data-testid="edit-button"
        >
          <Icon icon="mdi:pencil" className="mr-1.5" aria-hidden="true" /> Edit {schema.label}
        </ButtonWithTooltip>

        {!schema.kind?.match(/Core.*Group/g)?.length && ( // Hide group buttons on group list view
          <GroupsManagerTriggerButton
            schema={schema}
            permission={permission}
            objectId={objectDetailsData.id}
            className="text-custom-blue-600 p-4"
          />
        )}

        {!isGenericSchema(schema) && schema.inherit_from?.includes(GENERIC_REPOSITORY_KIND) && (
          <RepositoryActionMenu repositoryId={objectDetailsData.id} />
        )}

        <ButtonWithTooltip
          disabled={!permission.delete.isAllowed}
          tooltipEnabled
          tooltipContent={permission.delete.message ?? "Delete object"}
          data-testid="delete-button"
          variant={"danger"}
          size={"square"}
          onClick={() => setShowDeleteModal(true)}
        >
          <Icon icon="mdi:trash-can-outline" className="" aria-hidden="true" />
        </ButtonWithTooltip>
      </div>

      <SlideOver
        title={
          <SlideOverTitle
            schema={schema}
            currentObjectLabel={objectDetailsData.display_label}
            title={`Edit ${objectDetailsData.display_label}`}
            subtitle={schema.description}
          />
        }
        open={showEditModal}
        setOpen={setShowEditModal}
      >
        <ObjectItemEditComponent
          closeDrawer={() => setShowEditModal(false)}
          onUpdateComplete={() => graphqlClient.refetchQueries({ include: [schema.kind!] })}
          objectid={objectDetailsData.id!}
          objectname={schema.kind!}
        />
      </SlideOver>

      <ModalDeleteObject
        label={schema.label ?? schema.kind}
        rowToDelete={objectDetailsData}
        open={!!showDeleteModal}
        close={() => setShowDeleteModal(false)}
        onDelete={() => navigate(getObjectDetailsUrl2(schema.kind as string))}
      />
    </>
  );
}
