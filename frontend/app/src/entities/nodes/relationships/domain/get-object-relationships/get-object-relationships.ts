import { getObjectRelationshipsFromApi } from "@/entities/nodes/relationships/api/get-object-relationships-from-api";
import { NodeObject } from "@/entities/nodes/types";
import { ModelSchema } from "@/entities/schema/types";
import { Filter } from "@/shared/hooks/useFilters";

export type GetObjectRelationshipsParams = {
  parentKind: string;
  parentId: string;
  relationshipName: string;
  relationshipSchema: ModelSchema;
  branchName: string;
  atDate: Date | null;
  limit?: number;
  offset?: number;
  filters?: Array<Filter>;
};

export type GetObjectRelationships = (
  params: GetObjectRelationshipsParams
) => Promise<Array<NodeObject>>;

export const getObjectRelationships: GetObjectRelationships = async ({
  parentKind,
  relationshipName,
  ...params
}) => {
  const { data } = await getObjectRelationshipsFromApi({
    parentKind,
    relationshipName,
    ...params,
  });

  return (
    data[parentKind]?.edges?.[0]?.node?.[relationshipName]?.edges?.map(
      ({ node }: { node: NodeObject }) => node
    ) ?? []
  );
};
