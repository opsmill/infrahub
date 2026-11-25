import type { getValidatorDetailsFromApi } from "@/entities/diff/api/get-validator-details-from-api";
import type { getCheckDetails } from "@/entities/diff/domain/use-cases/get-check-details";
import type { getValidators } from "@/entities/diff/domain/use-cases/get-validators";

type DataCheck = Extract<
  NonNullable<Awaited<ReturnType<typeof getCheckDetails>>>,
  { __typename: "CoreDataCheck" }
>;

type DataValidator = Extract<
  Awaited<ReturnType<typeof getValidators>>[number],
  { __typename: "CoreDataValidator" }
>;

type ArtifactCheck = Extract<
  NonNullable<Awaited<ReturnType<typeof getCheckDetails>>>,
  { __typename: "CoreArtifactCheck" }
>;

type ArtifactValidator = Extract<
  Awaited<ReturnType<typeof getValidators>>[number],
  { __typename: "CoreArtifactValidator" }
>;

export function generateArtifactCheck(overrides: Partial<ArtifactCheck> = {}): ArtifactCheck {
  return {
    __typename: "CoreArtifactCheck",
    id: "artifact-check",
    display_label: "Artifact check",
    name: { value: "Artifact check" },
    message: null,
    severity: { value: "info" },
    conclusion: { value: "success" },
    kind: { value: "ArtifactDefinition" },
    origin: null,
    created_at: null,
    storage_id: null,
    artifact_id: null,
    ...overrides,
  };
}

export function generateArtifactValidator(
  overrides: Partial<ArtifactValidator> = {}
): ArtifactValidator {
  return {
    __typename: "CoreArtifactValidator",
    id: "artifact-validator",
    display_label: "Artifact Validator: Startup Config",
    conclusion: { value: "failure" },
    state: { value: "completed" },
    started_at: { value: "2026-01-01T00:00:00Z" },
    completed_at: { value: "2026-01-01T00:00:01Z" },
    checks: { edges: [] },
    definition: {
      node: {
        __typename: "CoreArtifactDefinition",
        id: "artifact-definition",
        display_label: "Startup Config",
      },
    },
    ...overrides,
  };
}

export function generateValidatorDetails({
  validatorId,
  checkIds,
  count = checkIds.length,
}: {
  validatorId: string;
  checkIds: string[];
  count?: number;
}): Awaited<ReturnType<typeof getValidatorDetailsFromApi>> {
  return {
    data: {
      CoreValidator: {
        edges: [
          {
            node: {
              id: validatorId,
              checks: { count, edges: checkIds.map((id) => ({ node: { id } })) },
            },
          },
        ],
      },
    },
  };
}

export function generateDataCheck(overrides: Partial<DataCheck> = {}): DataCheck {
  return {
    __typename: "CoreDataCheck",
    id: "data-check",
    display_label: "Data check",
    name: { value: "Data check" },
    message: null,
    severity: { value: "info" },
    conclusion: { value: "success" },
    kind: { value: "DataIntegrity" },
    origin: null,
    created_at: null,
    conflicts: null,
    ...overrides,
  };
}

export function generateDataValidator(overrides: Partial<DataValidator> = {}): DataValidator {
  return {
    __typename: "CoreDataValidator",
    id: "data-validator",
    display_label: "Data Integrity",
    conclusion: { value: "failure" },
    state: { value: "completed" },
    started_at: { value: "2026-01-01T00:00:00Z" },
    completed_at: { value: "2026-01-01T00:00:01Z" },
    checks: { edges: [] },
    ...overrides,
  };
}
