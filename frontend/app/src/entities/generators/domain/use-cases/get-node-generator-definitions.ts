import type { ContextParams } from "@/shared/api/types";

import { getGeneratorDefinitionsForNodeFromApi } from "@/entities/generators/api/get-generator-definitions-for-node-from-api";
import {
  getTargetGroupKindCountsFromApi,
  TARGET_GROUP_ALIAS_PREFIX,
} from "@/entities/generators/api/get-target-group-kind-counts-from-api";
import type { NodeGeneratorDefinition } from "@/entities/generators/domain/model/node-generator-definition";
import { selectNodeGeneratorDefinitions } from "@/entities/generators/domain/rules/select-node-generator-definitions";

export interface GetNodeGeneratorDefinitionsParams extends ContextParams {
  nodeId: string;
  nodeKind: string;
}

export type GetNodeGeneratorDefinitionsResult = NodeGeneratorDefinition[];

export type GetNodeGeneratorDefinitions = (
  params: GetNodeGeneratorDefinitionsParams
) => Promise<GetNodeGeneratorDefinitionsResult>;

const isCountField = (value: unknown): value is { count: number } =>
  typeof value === "object" &&
  value !== null &&
  "count" in value &&
  typeof value.count === "number";

export const getNodeGeneratorDefinitions: GetNodeGeneratorDefinitions = async ({
  nodeId,
  nodeKind,
  branchName,
  atDate,
}) => {
  const { data } = await getGeneratorDefinitionsForNodeFromApi({ nodeId, branchName, atDate });

  const definitions = data.CoreGeneratorDefinition.edges.flatMap(({ node }) =>
    node ? [node] : []
  );
  const groupIds = [
    ...new Set(definitions.flatMap(({ targets }) => (targets.node?.id ? [targets.node.id] : []))),
  ];
  if (groupIds.length === 0) return [];

  const { data: countData } = await getTargetGroupKindCountsFromApi({
    nodeKind,
    groupIds,
    branchName,
    atDate,
  });
  const countByAlias = new Map(
    typeof countData === "object" && countData !== null ? Object.entries(countData) : []
  );
  const kindCountByGroupId = new Map(
    groupIds.map((groupId, index) => {
      const field = countByAlias.get(`${TARGET_GROUP_ALIAS_PREFIX}${index}`);
      return [groupId, isCountField(field) ? field.count : 0];
    })
  );

  return selectNodeGeneratorDefinitions({ definitions, kindCountByGroupId });
};
