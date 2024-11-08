import { ButtonWithTooltip } from "@/components/buttons/button-primitive";
import SlideOver, { SlideOverTitle } from "@/components/display/slide-over";
import ModalDeleteObject from "@/components/modals/modal-delete-object";
import { ARTIFACT_DEFINITION_OBJECT, GENERIC_REPOSITORY_KIND } from "@/config/constants";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { Generate } from "@/screens/artifacts/generate";
import { GroupsManagerTriggerButton } from "@/screens/groups/groups-manager-trigger-button";
import ObjectItemEditComponent from "@/screens/object-item-edit/object-item-edit-paginated";
import RepositoryActionMenu from "@/screens/repository/repository-action-menu";
import { IModelSchema } from "@/state/atoms/schema.atom";
import { isGeneric } from "@/utils/common";
import { Icon } from "@iconify-icon/react";
import { useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

type DetailsButtonsProps = {
  schema: IModelSchema;
  objectDetailsData: any;
};

export function DetailsButtons({ schema, objectDetailsData, permission }: DetailsButtonsProps) {
  const location = useLocation();
  const { objectid } = useParams();
  const navigate = useNavigate();

  const redirect = location.pathname.replace(objectid ?? "", "");

  const [showEditModal, setShowEditModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);

  return (
    <>
      <div className="flex items-center gap-2">
        {schema.kind === ARTIFACT_DEFINITION_OBJECT && <Generate />}

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

        {!isGeneric(schema) && schema.inherit_from?.includes(GENERIC_REPOSITORY_KIND) && (
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
        onDelete={() => navigate(redirect)}
      />
    </>
  );
}
