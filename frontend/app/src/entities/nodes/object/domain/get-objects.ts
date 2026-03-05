import type { AddAttributesToRequestOptions } from "@/shared/api/graphql/utils";
import type { ContextParams, PaginationParams } from "@/shared/api/types";
import type { Filter } from "@/shared/hooks/useFilters";
import { DEFAULT_PAGE_SIZE } from "@/shared/utils/pagination";

import { getObjectsFromApi } from "@/entities/nodes/object/api/get-objects-from-api";
import { getAttributesVisibleInListView } from "@/entities/nodes/object/utils/get-attributes-visible-in-list-view";
import { getRelationshipsVisibleInListView } from "@/entities/nodes/object/utils/get-relationships-visible-in-list-view";
import type { NodeObject } from "@/entities/nodes/types";
import type { AttributeSchema, ModelSchema, RelationshipSchema } from "@/entities/schema/types";

export type GetObjectsParams = ContextParams &
  PaginationParams & {
    schema: ModelSchema;
    filters?: Array<Filter>;
    getAttributesVisible?: (attributes: AttributeSchema[]) => AttributeSchema[];
    getRelationshipsVisible?: (relationships: RelationshipSchema[]) => RelationshipSchema[];
    attributesOptions?: AddAttributesToRequestOptions;
    relationshipsOptions?: AddAttributesToRequestOptions;
  };

export type GetObjects = (args: GetObjectsParams) => Promise<Array<NodeObject>>;

export const getObjects: GetObjects = async ({
  schema,
  limit = DEFAULT_PAGE_SIZE,
  offset,
  branchName,
  atDate,
  filters,
  getAttributesVisible = getAttributesVisibleInListView,
  getRelationshipsVisible = getRelationshipsVisibleInListView,
  attributesOptions,
  relationshipsOptions,
}) => {
  const attributesVisible = getAttributesVisible(schema.attributes ?? []);
  const relationshipsVisible = getRelationshipsVisible(schema.relationships ?? []);

  const schemaKind = schema.kind as string;

  const { data, errors } = await getObjectsFromApi({
    schemaKind,
    attributes: attributesVisible,
    relationships: relationshipsVisible,
    limit,
    offset,
    branchName,
    atDate,
    filters,
    attributesOptions,
    relationshipsOptions,
  });

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return data[schemaKind]?.edges?.map(({ node }: { node: NodeObject }) => node) ?? [];
};
