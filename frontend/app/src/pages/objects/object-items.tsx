import { useParams } from "react-router";

import ErrorScreen from "@/shared/components/errors/error-screen";
import Content from "@/shared/components/layout/content";

import { ObjectItemsHeader } from "@/entities/nodes/object/ui/object-items-header";
import { ObjectsManager } from "@/entities/nodes/object/ui/objects-manager";
import { GENERIC_REPOSITORY_KIND } from "@/entities/repository/domain/model/repository";
import { REPOSITORY_COLUMN_SURFACE } from "@/entities/repository/domain/rules/repository-column-surface";
import { isOfKind } from "@/entities/schema/domain/rules/is-of-kind";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

function ObjectItemsPage() {
  const { objectKind } = useParams();

  const { schema } = useSchema(objectKind);

  if (!schema) return <ErrorScreen message={`Schema ${objectKind} not found.`} />;

  return (
    <Content.Card>
      <ObjectItemsHeader schema={schema} />

      <ObjectsManager
        schema={schema}
        columnSurface={
          isOfKind(GENERIC_REPOSITORY_KIND, schema) ? REPOSITORY_COLUMN_SURFACE : undefined
        }
      />
    </Content.Card>
  );
}

export const Component = ObjectItemsPage;
