import type { CheckType } from "@/shared/api/graphql/generated/types";

import type { RelationshipKind } from "@/entities/nodes/object/domain/model/node";
import { PROPOSED_CHANGE_OBJECT } from "@/entities/proposed-changes/domain/model/proposed-change";

export const NODE_OBJECT = "CoreNode";

export const PROFILE_KIND = "CoreProfile";

export const TEMPLATE_GENERIC_KIND = "CoreObjectTemplate";

export const FILE_OBJECT_KIND = "CoreFileObject";

export const CHECK_OBJECT = "CoreCheck";

export const GRAPHQL_QUERY_OBJECT = "CoreGraphQLQuery";

export const PROPOSED_CHANGES_VALIDATOR_OBJECT = "CoreValidator";

export const MENU_EXCLUDELIST = [
  PROPOSED_CHANGE_OBJECT,
  "CoreChangeComment",
  "CoreChangeThread",
  "CoreFileThread",
  "CoreArtifactThread",
  "CoreObjectThread",
  "InternalRefreshToken",
  "CoreThreadComment",
  "CoreArtifactCheck",
  "CoreArtifactTarget",
  "CoreCheck",
  "CoreComment",
  "CoreGeneratorCheck",
  "CoreGeneratorValidator",
  "CoreNode",
  "CoreStandardCheck",
  "CoreTaskTarget",
  "CoreThread",
  "CoreDataCheck",
  "CoreFileCheck",
  "CoreSchemaCheck",
  "CoreSchemaValidator",
  "CoreDataValidator",
  "CoreRepositoryValidator",
  "CoreArtifactValidator",
  "CoreUserValidator",
  "CoreValidator",
  "LineageOwner",
  "LineageSource",
];

export const NODE_PATH_EXCLUDELIST = ["property"];

export const VALIDATION_STATES = {
  QUEUED: "queued",
  IN_PROGRESS: "in_progress",
  COMPLETED: "completed",
};

export const VALIDATION_CONCLUSIONS = {
  UNKNOWN: "unknown",
  FAILURE: "failure",
  SUCCESS: "success",
};

export const CHECKS_LABEL = {
  EMPTY: "Empty",
  UNKOWN: "Unkown",
  QUEUED: "Queued",
  FAILURE: "Failure",
  SUCCESS: "Success",
  IN_PROGRESS: "In progress",
};

export const VALIDATIONS_ENUM_MAP: { [key: string]: CheckType } = {
  CoreArtifactValidator: "ARTIFACT",
  CoreDataValidator: "DATA",
  CoreGeneratorValidator: "GENERATOR",
  CoreRepositoryValidator: "REPOSITORY",
  CoreSchemaValidator: "SCHEMA",
  CoreUserValidator: "USER",
  all: "ALL",
};

export const MAX_VALUE_LENGTH_DISPLAY = 40;
export const MAX_PASSWORD_DOTS_DISPLAY = 20;

export const attributesKindForDetailsViewExclude = ["HashedPassword"];

export const relationshipsForListView = {
  one: ["Attribute", "Hierarchy", "Parent"],
  many: ["Attribute"],
};

export const relationshipsForDetailsView: { one: RelationshipKind[]; many: RelationshipKind[] } = {
  one: ["Generic", "Attribute", "Component", "Parent", "Hierarchy"],
  many: ["Attribute", "Parent"],
};

export const relationshipKindForForm: Array<RelationshipKind> = ["Attribute", "Parent"];

export const SEARCH_ANY_FILTER = "any__value";

export const SEARCH_PARTIAL_MATCH = "partial_match";

export const SEARCH_FILTERS = [SEARCH_ANY_FILTER, SEARCH_PARTIAL_MATCH];
