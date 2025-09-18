import { Icon } from "@iconify-icon/react";
import { useState } from "react";
import { useNavigate } from "react-router";

import { GENERIC_REPOSITORY_KIND } from "@/config/constants";

import { queryClient } from "@/shared/api/rest/client";
import { ButtonWithTooltip } from "@/shared/components/buttons/button-primitive";
import SlideOver, { SlideOverTitle } from "@/shared/components/display/slide-over";
import ModalDeleteObject from "@/shared/components/modals/modal-delete-object";

import { ARTIFACT_DEFINITION_KIND } from "@/entities/artifacts/constants";
import { ArtifactGenerateButton } from "@/entities/artifacts/ui/artifact-generate-button";
import {
  GENERATOR_DEFINITION_KIND,
  GENERATOR_INSTANCE_KIND,
} from "@/entities/generators/constants";
import { GeneratorDefinitionRunButton } from "@/entities/generators/ui/generator-definition-run-button";
import { GeneratorRunButton } from "@/entities/generators/ui/generator-run-button";
import { GroupsManagerTriggerButton } from "@/entities/groups/ui/groups-manager-trigger-button";
import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";
import ObjectItemEditComponent from "@/entities/nodes/object-item-edit/object-item-edit-paginated";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import type { Permission } from "@/entities/permission/types";
import RepositoryActionMenu from "@/entities/repository/ui/repository-action-menu";
import type { ModelSchema } from "@/entities/schema/types";
import { isGenericSchema } from "@/entities/schema/utils/is-generic-schema";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";

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
        {schema.kind === ARTIFACT_DEFINITION_KIND && (
          <ArtifactGenerateButton artifactDefinitionId={objectDetailsData.id} />
        )}

        {isOfKind(GENERATOR_DEFINITION_KIND, schema) && (
          <GeneratorDefinitionRunButton
            generatorId={objectDetailsData.id}
            groupId={objectDetailsData.targets.node.id}
          />
        )}

        {isOfKind(GENERATOR_INSTANCE_KIND, schema) && (
          <GeneratorRunButton
            generatorId={objectDetailsData.definition.node.id}
            targetNodeIds={[objectDetailsData.object.node.id]}
          />
        )}

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
            className="p-4 text-custom-blue-600"
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
          onUpdateComplete={async () => {
            await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
            setShowEditModal(false);
          }}
          objectid={objectDetailsData.id!}
          objectname={schema.kind!}
        />
      </SlideOver>

      <ModalDeleteObject
        label={schema.label ?? schema.kind}
        rowToDelete={objectDetailsData}
        open={!!showDeleteModal}
        close={() => setShowDeleteModal(false)}
        onDelete={() => navigate(getObjectDetailsUrl(schema.kind as string))}
      />
    </>
  );
}
