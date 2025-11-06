import { useLocation, useParams } from "react-router";

import { ARTIFACT_OBJECT, PROFILE_KIND, TEMPLATE_GENERIC_KIND } from "@/config/constants";

import { BreadcrumbObjectDetails } from "@/shared/components/layout/breadcrumb-navigation/breadcrumb-object-details";
import { BreadcrumbObjectDetailsHierarchy } from "@/shared/components/layout/breadcrumb-navigation/breadcrumb-object-details-hierarchy";
import { BreadcrumbItemSchema } from "@/shared/components/layout/breadcrumb-navigation/items/breadcrumb-item-schema";
import { Breadcrumb } from "@/shared/components/ui/breadcrumb";

import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { isHierarchicalSchema } from "@/entities/schema/utils/is-hierarchical-schema";

import { BreadcrumbSchemaHierarchy } from "./breadcrumb-schema-hierarchy";

export function BreadcrumbObjects() {
  const { objectKind, objectid, objectId, artifactId } = useParams();
  const { pathname } = useLocation();

  // For CoreArtifact route, objectKind is hardcoded in the path
  const isArtifactRoute = pathname.includes(`/objects/${ARTIFACT_OBJECT}`);
  const actualObjectKind = isArtifactRoute ? ARTIFACT_OBJECT : objectKind;

  const { schema, isProfile, isTemplate } = useSchema(actualObjectKind);

  if (!schema) {
    return null;
  }

  const objId = objectId ?? objectid ?? artifactId;

  if (isHierarchicalSchema(schema)) {
    return (
      <Breadcrumb>
        {objId ? (
          <BreadcrumbObjectDetailsHierarchy objectSchema={schema} objectId={objId} />
        ) : (
          <BreadcrumbSchemaHierarchy schema={schema} />
        )}
      </Breadcrumb>
    );
  }

  return (
    <Breadcrumb>
      {isProfile && <BreadcrumbItemSchema kind={PROFILE_KIND} />}
      {isTemplate && <BreadcrumbItemSchema kind={TEMPLATE_GENERIC_KIND} />}
      {objId ? (
        <BreadcrumbObjectDetails objectSchema={schema} objectId={objId} />
      ) : (
        <BreadcrumbItemSchema kind={schema.kind!} />
      )}
    </Breadcrumb>
  );
}
