import { Icon } from "@iconify-icon/react";
import { PencilLineIcon } from "lucide-react";
import { useState } from "react";

import { queryClient } from "@/shared/api/rest/client";
import { constructPath } from "@/shared/api/rest/fetch";
import SlideOver, { SlideOverTitle } from "@/shared/components/display/slide-over";
import { ButtonWithTooltip, LinkButton } from "@/shared/components/ui/button";
import { classNames } from "@/shared/utils/common";

import { ARTIFACT_DEFINITION_KIND } from "@/entities/artifacts/constants";
import { ArtifactGenerateButton } from "@/entities/artifacts/ui/artifact-generate-button";
import {
  GENERATOR_DEFINITION_KIND,
  GENERATOR_INSTANCE_KIND,
} from "@/entities/generators/constants";
import { GeneratorDefinitionRunButton } from "@/entities/generators/ui/generator-definition-run-button";
import { GeneratorRunButton } from "@/entities/generators/ui/generator-run-button";
import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import ObjectItemEditComponent from "@/entities/nodes/object-item-edit/object-item-edit-paginated";
import type { NodeObject } from "@/entities/nodes/types";
import type { Permission } from "@/entities/permission/types";
import type { ModelSchema } from "@/entities/schema/types";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";

type DetailsButtonsProps = {
  schema: ModelSchema;
  objectDetailsData: NodeObject;
  permission: Permission;
  className?: string;
};

export function DetailsButtons({
  schema,
  objectDetailsData,
  permission,
  className,
}: DetailsButtonsProps) {
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);

  const nodeLabel = getNodeLabel(objectDetailsData);
  const { isAllowed: isEditAllowed, message: editTooltipMessage } = permission.update;

  return (
    <>
      <div className={classNames("flex items-center gap-2", className)}>
        {schema.kind === ARTIFACT_DEFINITION_KIND && (
          <ArtifactGenerateButton artifactDefinitionId={objectDetailsData.id} size="sm" />
        )}

        {isOfKind(GENERATOR_DEFINITION_KIND, schema) && (
          <GeneratorDefinitionRunButton
            generatorId={objectDetailsData.id}
            groupId={objectDetailsData.targets.node.id}
            size="sm"
          />
        )}

        {isOfKind(GENERATOR_INSTANCE_KIND, schema) && (
          <GeneratorRunButton
            generatorId={objectDetailsData.definition.node.id}
            targetNodeIds={[objectDetailsData.object.node.id]}
            size="sm"
          />
        )}

        <ButtonWithTooltip
          variant="outline"
          size="sm"
          disabled={!isEditAllowed}
          onClick={() => setIsEditModalOpen(true)}
          tooltipContent={editTooltipMessage}
          tooltipEnabled={!isEditAllowed}
          data-testid="edit-button"
        >
          <PencilLineIcon className="mr-1 size-3.5" />
          Edit
        </ButtonWithTooltip>

        <LinkButton
          variant="outline"
          size="sm"
          to={constructPath("/schema", [{ name: "kind", value: schema.kind }])}
        >
          <Icon icon="mdi:code-json" className="mr-1" />
          Schema
        </LinkButton>
      </div>

      <SlideOver
        title={
          <SlideOverTitle
            schema={schema}
            currentObjectLabel={nodeLabel}
            title={`Edit ${nodeLabel}`}
            subtitle={schema.description}
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
          objectId={objectDetailsData.id!}
          objectname={schema.kind!}
        />
      </SlideOver>
    </>
  );
}
