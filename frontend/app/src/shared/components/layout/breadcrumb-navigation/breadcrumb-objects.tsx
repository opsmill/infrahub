import { useParams } from "react-router";

import { BreadcrumbObject } from "@/shared/components/layout/breadcrumb-navigation/breadcrumb-object";
import { BreadcrumbObjectHierarchy } from "@/shared/components/layout/breadcrumb-navigation/breadcrumb-object-hierarchy";
import { BreadcrumbItemSchema } from "@/shared/components/layout/breadcrumb-navigation/items/breadcrumb-item-schema";
import { Breadcrumb, BreadcrumbSeparator } from "@/shared/components/ui/breadcrumb";

import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { isHierarchicalSchema } from "@/entities/schema/utils/is-hierarchical-schema";

import { BreadcrumbSchemaHierarchy } from "./breadcrumb-schema-hierarchy";

export function BreadcrumbObjects() {
  const { objectKind, objectid, objectId, artifactId } = useParams();
  const { schema } = useSchema(objectKind);

  if (!schema) {
    return null;
  }

  const objId = objectId ?? objectid ?? artifactId;

  if (isHierarchicalSchema(schema)) {
    return (
      <Breadcrumb>
        {objId ? (
          <BreadcrumbObjectHierarchy objectSchema={schema} objectId={objId} />
        ) : (
          <BreadcrumbSchemaHierarchy schema={schema} />
        )}
      </Breadcrumb>
    );
  }

  return (
    <Breadcrumb>
      <BreadcrumbSeparator />
      {objId ? (
        <BreadcrumbObject objectSchema={schema} objectId={objId} />
      ) : (
        <BreadcrumbItemSchema schema={schema} />
      )}
    </Breadcrumb>
  );
}
