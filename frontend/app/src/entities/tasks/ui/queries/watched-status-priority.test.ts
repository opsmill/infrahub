import { ApolloLink, execute, gql, Observable } from "@apollo/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import graphqlClient, { priorityLink } from "@/shared/api/graphql/graphqlClientApollo";
import { PRIORITY_HEADER } from "@/shared/api/priority";

import { getBranchTaskStatusFromApi } from "@/entities/tasks/api/get-branch-task-status-from-api";
import { getTaskListFromApi } from "@/entities/tasks/api/get-task-list-from-api";

// FR-005: watched live-status polls must inherit `high`. These are guard tests,
// not behaviour tests — they observe the header the PRODUCTION injection path
// (the exported `priorityLink`, the same setContext link wired into the app's
// Apollo chain) stamps for the exact operation context each watched query hands
// to `graphqlClient.query`. Because these queries declare no `context.priority`,
// `resolvePriority` defaults to `high`. If someone later demotes one by adding
// `context: { priority: 'low' }`, the captured context flows through
// `priorityLink`, the header flips to `low`, and the matching test fails.

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

// Capture the options a watched from-api call passes to graphqlClient.query,
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

describe("watched task polls emit X-Priority: high (FR-005)", () => {
  afterEach(() => vi.restoreAllMocks());

  it("task-list poll (get-task-list.query.ts) inherits high", async () => {
    const context = await capturedContext(() => getTaskListFromApi());
    expect(await priorityHeaderForContext(context)).toBe("high");
  });

  it("task-status poll (is-task-running-on-branch.query.ts) inherits high", async () => {
    const context = await capturedContext(() => getBranchTaskStatusFromApi("main"));
    expect(await priorityHeaderForContext(context)).toBe("high");
  });
});
