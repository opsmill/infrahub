import { GENERIC_REPOSITORY_KIND } from "@/shared/config/constants";
import { classNames } from "@/shared/utils/common";

import { ARTIFACT_DEFINITION_KIND } from "@/entities/artifacts/constants";
import { ArtifactGenerateButton } from "@/entities/artifacts/ui/artifact-generate-button";
import {
  GENERATOR_DEFINITION_KIND,
  GENERATOR_INSTANCE_KIND,
} from "@/entities/generators/constants";
import { GeneratorDefinitionRunButton } from "@/entities/generators/ui/generator-definition-run-button";
import { GeneratorRunButton } from "@/entities/generators/ui/generator-run-button";
import type { NodeObject } from "@/entities/nodes/types";
import RepositoryActionMenu from "@/entities/repository/ui/repository-action-menu";
import type { ModelSchema } from "@/entities/schema/types";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";

type DetailsButtonsProps = {
  schema: ModelSchema;
  objectDetailsData: NodeObject;
  className?: string;
};

export function DetailsButtons({ schema, objectDetailsData, className }: DetailsButtonsProps) {
  return (
    <>
      <div className={classNames("flex items-center gap-2", className)}>
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

        {isOfKind(GENERIC_REPOSITORY_KIND, schema) && (
          <RepositoryActionMenu repositoryId={objectDetailsData.id} />
        )}
      </div>
    </>
  );
}
