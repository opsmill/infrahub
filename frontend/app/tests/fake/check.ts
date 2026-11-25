import type { getArtifactValidatorDetailsFromApi } from "@/entities/diff/api/get-artifact-validator-details-from-api";
import type { getCheckDetails } from "@/entities/diff/domain/use-cases/get-check-details";
import type { getValidators } from "@/entities/diff/domain/use-cases/get-validators";

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

export function generateArtifactValidatorDetails({
  validatorId,
  checkIds,
  count = checkIds.length,
}: {
  validatorId: string;
  checkIds: string[];
  count?: number;
}): Awaited<ReturnType<typeof getArtifactValidatorDetailsFromApi>> {
  return {
    data: {
      CoreArtifactValidator: {
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
