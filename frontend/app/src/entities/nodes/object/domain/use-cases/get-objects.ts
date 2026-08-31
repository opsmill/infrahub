import type { AddAttributesToRequestOptions } from "@/shared/api/graphql/utils";
import type { ContextParams, PaginationParams } from "@/shared/api/types";
import { DEFAULT_PAGE_SIZE } from "@/shared/utils/pagination";

import type { Filter } from "@/entities/nodes/filters/domain/model/filter";
import { getObjectsFromApi } from "@/entities/nodes/object/api/get-objects-from-api";
import type { NodeObject } from "@/entities/nodes/object/domain/model/node";
import { getAttributesVisibleInListView } from "@/entities/nodes/object/domain/rules/get-attributes-visible-in-list-view";
import { getRelationshipsVisibleInListView } from "@/entities/nodes/object/domain/rules/get-relationships-visible-in-list-view";
import type { Sort } from "@/entities/nodes/sort/domain/model/sort";
import type {
  AttributeSchema,
  ModelSchema,
  RelationshipSchema,
} from "@/entities/schema/domain/model/schema";

export type GetObjectsParams = ContextParams &
  PaginationParams & {
    schema: ModelSchema;
    filters?: Array<Filter>;
    sort?: Array<Sort> | null;
    /**
     * Names of fields the user revealed in the list view. They are `display: "extra"` fields that
     * the default list-view rules exclude, so they must be opted back into the GraphQL selection
     * set or their columns would render empty cells.
     */
    revealedFields?: readonly string[];
    getAttributesVisible?: (
      attributes: AttributeSchema[],
      revealedNames?: ReadonlySet<string>
    ) => AttributeSchema[];
    getRelationshipsVisible?: (
      relationships: RelationshipSchema[],
      revealedNames?: ReadonlySet<string>
    ) => RelationshipSchema[];
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
  sort,
  revealedFields,
  getAttributesVisible = getAttributesVisibleInListView,
  getRelationshipsVisible = getRelationshipsVisibleInListView,
  attributesOptions,
  relationshipsOptions,
}) => {
  // `new Set(undefined)` is the empty set, which is exactly "reveal nothing" — no need to branch.
  const revealed = new Set(revealedFields);
  const attributesVisible = getAttributesVisible(schema.attributes ?? [], revealed);
  const relationshipsVisible = getRelationshipsVisible(schema.relationships ?? [], revealed);

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
    sort,
    attributesOptions,
    relationshipsOptions,
  });

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return data[schemaKind]?.edges?.map(({ node }: { node: NodeObject }) => node) ?? [];
};
