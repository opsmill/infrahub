export const ADMIN_MENU_ITEMS = [
  {
    path: "/schema",
    label: "Schema",
  },
  {
    path: "/groups",
    label: "Groups",
  },
];

export const BRANCHES_MENU_ITEMS = [
  {
    path: "/branches",
    label: "List",
  },
  {
    path: "/proposed-changes",
    label: "Proposed changes",
  },
];

export const DEFAULT_BRANCH_NAME = "main";

export const ACCESS_TOKEN_KEY = "access_token";

export const REFRESH_TOKEN_KEY = "refresh_token";

export const ACCOUNT_OBJECT = "Account";

export const ACCOUNT_TOKEN_OBJECT = "AccountToken";

export const ARTIFACT_DEFINITION_OBJECT = "CoreArtifactDefinition";

export const PROPOSED_CHANGES = "ProposedChange";
export const PROPOSED_CHANGES_OBJECT = "CoreProposedChange";

export const PROPOSED_CHANGES_THREAD = "Thread";
export const PROPOSED_CHANGES_THREAD_OBJECT = "CoreThread";

export const PROPOSED_CHANGES_CHANGE_THREAD = "ChangeThread";
export const PROPOSED_CHANGES_CHANGE_THREAD_OBJECT = "CoreChangeThread";

export const PROPOSED_CHANGES_FILE_THREAD = "FileThread";
export const PROPOSED_CHANGES_FILE_THREAD_OBJECT = "CoreFileThread";

export const PROPOSED_CHANGES_OBJECT_THREAD = "ObjectThread";
export const PROPOSED_CHANGES_OBJECT_THREAD_OBJECT = "CoreObjectThread";

export const ARTIFACT_OBJECT = "Artifact";
export const PROPOSED_CHANGES_ARTIFACT_THREAD = "ArtifactThread";
export const PROPOSED_CHANGES_ARTIFACT_THREAD_OBJECT = "CoreArtifactThread";

export const PROPOSED_CHANGES_COMMENT_OBJECT = "CoreChangeComment";

export const PROPOSED_CHANGES_THREAD_COMMENT_OBJECT = "CoreThreadComment";

export const PROPOSED_CHANGES_VALIDATOR_OBJECT = "CoreValidator";

export const GROUP_OBJECT = "Group";

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
  "CoreStandardGroup",
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

export const ATTRIBUTES_EXCLUDELIST = ["HashedPassword"];

export const COLUMNS_EXCLUDELIST = ["TextArea", "JSON"];

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

["CoreArtifactValidator", "CoreDataValidator", "CoreRepositoryValidator", "CoreSchemaValidator"];

export const VALIDATIONS_ENUM_MAP: { [key: string]: string } = {
  CoreArtifactValidator: "ARTIFACT",
  CoreDataValidator: "DATA",
  CoreRepositoryValidator: "REPOSITORY",
  CoreSchemaValidator: "SCHEMA",
  all: "ALL",
};

export const MAX_VALUE_LENGTH_DISPLAY = 50;
