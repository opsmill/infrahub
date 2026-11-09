import type { CheckType } from "@/shared/api/graphql/generated/types";

export const CHECK_OBJECT = "CoreCheck";
export const VALIDATOR_OBJECT = "CoreValidator";

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

export const VALIDATIONS_ENUM_MAP: { [key: string]: CheckType } = {
  CoreArtifactValidator: "ARTIFACT",
  CoreDataValidator: "DATA",
  CoreGeneratorValidator: "GENERATOR",
  CoreRepositoryValidator: "REPOSITORY",
  CoreSchemaValidator: "SCHEMA",
  CoreUserValidator: "USER",
  all: "ALL",
};
