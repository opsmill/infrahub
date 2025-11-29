import type { CheckType } from "@/shared/api/graphql/generated/graphql";

import type { RelationshipKind } from "@/entities/nodes/types";
import { PROPOSED_CHANGE_OBJECT } from "@/entities/proposed-changes/constants";

export const DEFAULT_BRANCH_NAME = "main";

export const REFRESH_TOKEN_KEY = "refresh_token";

export const NODE_OBJECT = "CoreNode";

export const PROFILE_KIND = "CoreProfile";

export const TEMPLATE_GENERIC_KIND = "CoreObjectTemplate";

export const TASK_TARGET = "CoreTaskTarget";

export const ACCOUNT_GENERIC_OBJECT = "CoreGenericAccount";
export const ACCOUNT_OBJECT = "CoreAccount";

export const ACCOUNT_GROUP_OBJECT = "CoreAccountGroup";

export const ACCOUNT_ROLE_OBJECT = "CoreAccountRole";

export const ACCOUNT_PERMISSION_OBJECT = "CoreBasePermission";
export const GLOBAL_PERMISSION_OBJECT = "CoreGlobalPermission";
export const OBJECT_PERMISSION_OBJECT = "CoreObjectPermission";

export const GENERIC_REPOSITORY_KIND = "CoreGenericRepository";

export const REPOSITORY_KIND = "CoreRepository";

export const READONLY_REPOSITORY_KIND = "CoreReadOnlyRepository";

export const ACCOUNT_TOKEN_OBJECT = "InfrahubAccountToken";

export const ARTIFACT_DEFINITION_OBJECT = "CoreArtifactDefinition";

export const PROPOSED_CHANGES_OBJECT = "CoreProposedChange";

export const PROPOSED_CHANGES_THREAD_OBJECT = "CoreThread";

export const PROPOSED_CHANGES_CHANGE_THREAD_OBJECT = "CoreChangeThread";

export const PROPOSED_CHANGES_OBJECT_THREAD_OBJECT = "CoreObjectThread";

export const PROPOSED_CHANGES_FILE_THREAD_OBJECT = "CoreFileThread";

export const PROPOSED_CHANGES_ARTIFACT_THREAD_OBJECT = "CoreArtifactThread";

export const ARTIFACT_OBJECT = "CoreArtifact";

export const CHECK_OBJECT = "CoreCheck";

export const GRAPHQL_QUERY_OBJECT = "CoreGraphQLQuery";

export const PROPOSED_CHANGES_THREAD_COMMENT_OBJECT = "CoreThreadComment";

export const PROPOSED_CHANGES_VALIDATOR_OBJECT = "CoreValidator";

export const NUMBER_POOL_OBJECT = "CoreNumberPool";

export const TASK_OBJECT = "InfrahubTask";

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

export const RELATIONSHIP_VIEW_BLACKLIST = [
  "member_of_groups",
  "subscriber_of_groups",
  "children",
  "profiles",
];

export const relationshipKindForForm: Array<RelationshipKind> = ["Attribute", "Parent"];

export const PROPOSED_CHANGES_EDITABLE_STATE = ["open", "closed"];

export const TASK_TAB = "tasks";

export const SEARCH_ANY_FILTER = "any__value";

export const SEARCH_PARTIAL_MATCH = "partial_match";

export const SEARCH_FILTERS = [SEARCH_ANY_FILTER, SEARCH_PARTIAL_MATCH];

export const DIFF_TABS = {
  DATA: "data",
  FILES: "files",
  ARTIFACTS: "artifacts",
  SCHEMA: "schema",
  CHECKS: "checks",
};
