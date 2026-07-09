import { Icon } from "@iconify-icon/react";
import { Button, LinkButton, Sheet, Tooltip } from "@infrahub/ui";
import { PencilLineIcon } from "lucide-react";
import { useState } from "react";

import { queryClient } from "@/shared/api/rest/client";
import { constructPath } from "@/shared/api/rest/fetch";
import { SlideOverTitle } from "@/shared/components/display/slide-over";
import { classNames } from "@/shared/utils/common";

import { ARTIFACT_DEFINITION_KIND } from "@/entities/artifacts/domain/model/artifact";
import { ArtifactGenerateButton } from "@/entities/artifacts/ui/artifact-generate-button";
import {
  GENERATOR_DEFINITION_KIND,
  GENERATOR_INSTANCE_KIND,
} from "@/entities/generators/domain/model/generator";
import { GeneratorDefinitionRunButton } from "@/entities/generators/ui/generator-definition-run-button";
import { GeneratorRunButton } from "@/entities/generators/ui/generator-run-button";
import type { NodeObject } from "@/entities/nodes/object/domain/model/node";
import { getNodeLabel } from "@/entities/nodes/object/domain/rules/get-node-label";
import ObjectEdit from "@/entities/nodes/object/ui/object-edit/object-item-edit-paginated";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import type { Permission } from "@/entities/permission/domain/model/permission";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { isOfKind } from "@/entities/schema/domain/rules/is-of-kind";

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

        <Tooltip message={editTooltipMessage}>
          <Button
            variant="outline"
            size="sm"
            isDisabledAndFocusable={!isEditAllowed}
            onPress={() => setIsEditModalOpen(true)}
            data-testid="edit-button"
          >
            <PencilLineIcon className="size-3.5" />
            Edit
          </Button>
        </Tooltip>

        <LinkButton
          variant="outline"
          size="sm"
          href={constructPath("/schema", [{ name: "kind", value: schema.kind }])}
        >
          <Icon icon="mdi:code-json" />
          Schema
        </LinkButton>
      </div>

      <Sheet isOpen={isEditModalOpen} onOpenChange={setIsEditModalOpen}>
        <SlideOverTitle
          schema={schema}
          currentObjectLabel={nodeLabel}
          title={`Edit ${nodeLabel}`}
          subtitle={schema.description}
        />
        <ObjectEdit
          closeDrawer={() => setIsEditModalOpen(false)}
          onUpdateComplete={async () => {
            await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
            setIsEditModalOpen(false);
          }}
          objectId={objectDetailsData.id!}
          objectKind={schema.kind!}
        />
      </Sheet>
    </>
  );
}
