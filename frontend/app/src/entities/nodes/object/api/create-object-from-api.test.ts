import { ApolloLink, execute, gql, Observable } from "@apollo/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import graphqlClient, { priorityLink } from "@/shared/api/graphql/graphqlClientApollo";
import { PRIORITY_HEADER } from "@/shared/api/priority";

import { createObjectFromApi } from "./create-object-from-api";

describe("createObjectFromApi — file upload inherits X-Priority: high", () => {
  // A file upload rides the shared Apollo `createUploadLink` (the terminating
  // httpLink), so it passes through `priorityLink` like any other operation.
  // A full multipart HTTP request needs the browser upload path (createUploadLink
  // builds FormData from a real File) and is exercised end-to-end by the E2E
  // suite (T031). Node mode proves the observable equivalent: the upload call
  // site never opts priority down, and its (priority-free) context stamps `high`
  // when run through the real exported priorityLink.
  let mutateSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.stubGlobal("localStorage", {
      getItem: () => null,
      setItem: () => {},
      removeItem: () => {},
      clear: () => {},
    });
    mutateSpy = vi.spyOn(graphqlClient, "mutate").mockResolvedValue({ data: {} } as never);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  // Observe the header at the transport boundary: a terminating link records the
  // context headers the priority link produced, mirroring the graphqlClientApollo
  // test's forward pattern.
  function runThroughPriorityLink(context?: Record<string, unknown>) {
    let captured: Record<string, unknown> | undefined;

    const captureLink = new ApolloLink((operation) => {
      captured = operation.getContext().headers as Record<string, unknown>;
      return Observable.of({ data: null });
    });

    const link = ApolloLink.from([priorityLink, captureLink]);

    return new Promise<Record<string, unknown> | undefined>((resolve, reject) => {
      execute(link, { query: gql`{ __typename }`, context }).subscribe({
        complete: () => resolve(captured),
        error: (err) => reject(err),
      });
    });
  }

  it("issues a multipart mutation whose priority-free context inherits high via priorityLink", async () => {
    const file = new File(["hello"], "upload.txt", { type: "text/plain" });

    await createObjectFromApi({
      objectKind: "TestThing",
      data: { name: { value: "x" } },
      branchName: "main",
      file,
    });

    expect(mutateSpy).toHaveBeenCalledOnce();
    const call = mutateSpy.mock.calls[0]?.[0] as {
      variables?: { file?: File };
      context?: Record<string, unknown>;
    };

    // Multipart: the File rides as a GraphQL `Upload` variable, so this mutation
    // goes through the shared createUploadLink (which is downstream of priorityLink).
    expect(call.variables?.file).toBe(file);

    // The upload call site sets only `branch` in context — crucially NO `priority`
    // key — so it inherits the default rather than opting down.
    expect(call.context).toBeDefined();
    expect(call.context && "priority" in call.context).toBe(false);

    // Tie the call-site context to the observable outbound header: the exact
    // context the upload uses, run through the real priorityLink, stamps `high`.
    const headers = await runThroughPriorityLink(call.context);
    expect(headers?.[PRIORITY_HEADER]).toBe("high");
  });
});
