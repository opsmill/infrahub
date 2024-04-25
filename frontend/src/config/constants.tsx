import { SchemaAttributeType } from "../screens/edit-form-hook/dynamic-control-types";

export const DEFAULT_BRANCH_NAME = "main";

export const ACCESS_TOKEN_KEY = "access_token";

export const REFRESH_TOKEN_KEY = "refresh_token";

export const NODE_OBJECT = "CoreNode";

export const PROFILE_KIND = "CoreProfile";

export const TASK_TARGET = "CoreTaskTarget";

export const DATA_CHECK_OBJECT = "CoreDataCheck";

export const ACCOUNT_OBJECT = "CoreAccount";

export const ACCOUNT_SELF_UPDATE_OBJECT = "CoreAccountSelf";

export const ACCOUNT_TOKEN_OBJECT = "InternalAccountToken";

export const ARTIFACT_DEFINITION_OBJECT = "CoreArtifactDefinition";

export const PROPOSED_CHANGES_OBJECT = "CoreProposedChange";

export const PROPOSED_CHANGES_THREAD_OBJECT = "CoreThread";

export const PROPOSED_CHANGES_CHANGE_THREAD_OBJECT = "CoreChangeThread";

export const PROPOSED_CHANGES_FILE_THREAD_OBJECT = "CoreFileThread";

export const PROPOSED_CHANGES_OBJECT_THREAD_OBJECT = "CoreObjectThread";

export const ARTIFACT_OBJECT = "CoreArtifact";

export const PROPOSED_CHANGES_ARTIFACT_THREAD_OBJECT = "CoreArtifactThread";

export const PROPOSED_CHANGES_COMMENT_OBJECT = "CoreChangeComment";

export const PROPOSED_CHANGES_THREAD_COMMENT_OBJECT = "CoreThreadComment";

export const PROPOSED_CHANGES_VALIDATOR_OBJECT = "CoreValidator";

export const SCHEMA_DROPDOWN_ADD = "SchemaDropdownAdd";

export const SCHEMA_DROPDOWN_REMOVE = "SchemaDropdownRemove";

export const SCHEMA_ENUM_ADD = "SchemaEnumAdd";

export const SCHEMA_ENUM_REMOVE = "SchemaEnumRemove";

export const GROUP_OBJECT = "CoreGroup";

export const TASK_OBJECT = "InfrahubTask";

export const WRITE_ROLES = ["admin", "read-write"];

export const ADMIN_ROLES = ["admin"];

export const MENU_EXCLUDELIST = [
  "InternalAccountToken",
  "CoreChangeComment",
  "CoreChangeThread",
  "CoreFileThread",
  "CoreArtifactThread",
  "CoreObjectThread",
  "CoreProposedChange",
  "InternalRefreshToken",
  "CoreThreadComment",
  "CoreArtifactCheck",
  "CoreStandardCheck",
  "CoreDataCheck",
  "CoreFileCheck",
  "CoreSchemaCheck",
  "CoreSchemaValidator",
  "CoreDataValidator",
  "CoreRepositoryValidator",
  "CoreArtifactValidator",
];

export const ATTRIBUTES_NAME_EXCLUDELIST = ["checksum", "storage_id"];

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

export const CHECK_SEVERITY = {
  SUCCESS: "success",
  INFO: "info",
  WARNING: "warning",
  ERROR: "error",
  CRITICAL: "critical",
};

export const CHECK_CONCLUSIONS = {
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

export const VALIDATIONS_ENUM_MAP: { [key: string]: string } = {
  CoreArtifactValidator: "ARTIFACT",
  CoreDataValidator: "DATA",
  CoreRepositoryValidator: "REPOSITORY",
  CoreSchemaValidator: "SCHEMA",
  CoreUserValidator: "USER",
  all: "ALL",
};

export const MAX_VALUE_LENGTH_DISPLAY = 40;

export const attributesKindForListView = [
  "Text",
  "Number",
  "Boolean",
  "Dropdown",
  "Email",
  "URL",
  "File",
  "MacAddress",
  "Color",
  "Bandwidth",
  "IPHost",
  "IPNetwork",
  "DateTime",
];

export const SCHEMA_ATTRIBUTE_KIND: Record<string, SchemaAttributeType> = {
  ID: "ID",
  DROPDOWN: "Dropdown",
  TEXT: "Text",
  TEXTAREA: "TextArea",
  DATETIME: "DateTime",
  EMAIL: "Email",
  PASSWORD: "Password",
  HASHED_PASSWORD: "HashedPassword",
  URL: "URL",
  FILE: "File",
  MAC_ADDRESS: "MacAddress",
  COLOR: "Color",
  NUMBER: "Number",
  BANDWIDTH: "Bandwidth",
  IP_HOST: "IPHost",
  IP_NETWORK: "IPNetwork",
  CHECKBOX: "Checkbox",
  LIST: "List",
  JSON: "JSON",
  ANY: "Any",
  STRING: "String",
  INTEGER: "Integer",
  BOOLEAN: "Boolean",
} as const;

export const attributesKindForDetailsViewExclude = ["HashedPassword"];

export const relationshipsForListView = {
  one: ["Attribute", "Hierarchy"],
  many: ["Attribute"],
};

export const relationshipsForDetailsView = {
  one: ["Generic", "Attribute", "Component", "Parent", "Hierarchy"],
  many: ["Attribute", "Parent"],
};

export const relationshipsForTabs = {
  one: [],
  many: ["Generic", "Component", "Hierarchy"],
};

export const peersKindForForm = ["Attribute", "Parent"];

export const PROPOSED_CHANGES_EDITABLE_STATE = ["open", "closed"];

export const TASK_TAB = "tasks";

export const SEARCH_ANY_FILTER = "any__value";

export const SEARCH_PARTIAL_MATCH = "partial_match";

export const SEARCH_FILTERS = [SEARCH_ANY_FILTER, SEARCH_PARTIAL_MATCH];
