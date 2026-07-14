import { ApolloLink, execute, gql, Observable } from "@apollo/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import graphqlClient, { priorityLink } from "@/shared/api/graphql/graphqlClientApollo";
import { PRIORITY_HEADER } from "@/shared/api/priority";

import { getBranchActionStateFromApi } from "@/entities/branches/api/get-branch-action-state-from-api";

// FR-005: watched live-status polls must inherit `high`. This is a guard test,
// not a behaviour test — it observes the header the PRODUCTION injection path
// (the exported `priorityLink`, the same setContext link wired into the app's
// Apollo chain) stamps for the exact operation context the watched query hands
// to `graphqlClient.query`. Because this query declares no `context.priority`,
// `resolvePriority` defaults to `high`. If someone later demotes it by adding
// `context: { priority: 'low' }`, the captured context flows through
// `priorityLink`, the header flips to `low`, and this test fails.

// Run the real priorityLink over `context` and return the X-Priority it emits.
function priorityHeaderForContext(context: Record<string, unknown> | undefined) {
  let captured: Record<string, unknown> | undefined;
  const captureLink = new ApolloLink((operation) => {
    captured = operation.getContext().headers as Record<string, unknown>;
    return Observable.of({ data: null });
  });
  const link = ApolloLink.from([priorityLink, captureLink]);

  return new Promise<string | undefined>((resolve, reject) => {
    execute(link, { query: gql`{ __typename }`, context }).subscribe({
      complete: () => resolve(captured?.[PRIORITY_HEADER] as string | undefined),
      error: reject,
    });
  });
}

// Capture the options the watched from-api call passes to graphqlClient.query,
// without touching the network, and return its `context` (undefined = default).
async function capturedContext(invoke: () => Promise<unknown>) {
  const spy = vi.spyOn(graphqlClient, "query").mockResolvedValue({ data: {} } as any);
  try {
    await invoke();
    return spy.mock.calls.at(-1)?.[0]?.context as Record<string, unknown> | undefined;
  } finally {
    spy.mockRestore();
  }
}

describe("watched branch-action-state poll emits X-Priority: high (FR-005)", () => {
  afterEach(() => vi.restoreAllMocks());

  it("branch-action-state poll (get-branch-action-state.query.ts) inherits high", async () => {
    const context = await capturedContext(() =>
      getBranchActionStateFromApi({ branchName: "main", workflow: [], state: [] })
    );
    expect(await priorityHeaderForContext(context)).toBe("high");
  });
});
