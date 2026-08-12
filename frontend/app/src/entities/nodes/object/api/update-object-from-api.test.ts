import { type FieldNode, type OperationDefinitionNode, valueFromASTUntyped } from "graphql";
import { beforeEach, describe, expect, it, vi } from "vitest";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

import { updateObjectFromApi } from "./update-object-from-api";

vi.mock("@/shared/api/graphql/graphqlClientApollo", () => ({
  default: { mutate: vi.fn() },
}));

const getSentMutationData = () => {
  const mutateOptions = vi.mocked(graphqlClient.mutate).mock.calls[0]![0];
  const operation = mutateOptions.mutation.definitions.find(
    (definition): definition is OperationDefinitionNode => definition.kind === "OperationDefinition"
  )!;
  const mutationField = operation.selectionSet.selections[0] as FieldNode;
  const dataArgument = mutationField.arguments!.find((argument) => argument.name.value === "data")!;
  return valueFromASTUntyped(dataArgument.value, mutateOptions.variables);
};

describe("updateObjectFromApi", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(graphqlClient.mutate).mockResolvedValue({ data: {} });
  });

  it("sends JSON attribute values whose keys are not valid GraphQL names", async () => {
    // GIVEN a JSON attribute value with a key that cannot be expressed as a GraphQL name,
    // alongside a relationship input that must stay untouched
    const data = {
      id: "credential-1",
      name: { value: "deSEC" },
      settings: { value: { "auth-token": "pass://Domain Management/deSEC.io/auth-token" } },
      provider: { id: "provider-1" },
    };

    // WHEN
    await updateObjectFromApi({ data, objectKind: "DnsCredential", branchName: "main" });

    // THEN the mutation reaches the client with the JSON value intact
    expect(graphqlClient.mutate).toHaveBeenCalledTimes(1);
    expect(getSentMutationData()).toEqual({
      id: "credential-1",
      name: { value: "deSEC" },
      settings: { value: { "auth-token": "pass://Domain Management/deSEC.io/auth-token" } },
      provider: { id: "provider-1" },
    });
  });
});
