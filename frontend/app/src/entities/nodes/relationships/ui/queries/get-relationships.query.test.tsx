import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type React from "react";
import { describe, expect, test, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

import { BranchContext } from "@/entities/branches/ui/branches-provider";
import { useObjectsCount } from "@/entities/nodes/object/ui/queries/get-objects-count.query";
import { getRelationships } from "@/entities/nodes/relationships/domain/use-cases/get-relationships";
import { useRelationships } from "@/entities/nodes/relationships/ui/queries/get-relationships.query";

import { generateBranch } from "../../../../../../tests/fake/branch";

vi.mock("@/entities/nodes/relationships/domain/use-cases/get-relationships");
vi.mock("@/entities/nodes/object/ui/queries/get-objects-count.query");

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <BranchContext value={{ currentBranch: generateBranch(), setCurrentBranch: () => {} }}>
      {children}
    </BranchContext>
  </QueryClientProvider>
);

describe("useRelationships", () => {
  test("searches for the text without its surrounding whitespace", async () => {
    vi.mocked(useObjectsCount).mockReturnValue({
      data: 1,
      isSuccess: true,
      isError: false,
    } as ReturnType<typeof useObjectsCount>);
    vi.mocked(getRelationships).mockResolvedValue([]);

    await renderHook(() => useRelationships({ peer: "InfraDevice", search: "  spine1 " }), {
      wrapper,
    });

    expect(vi.mocked(useObjectsCount).mock.calls.at(-1)?.[0]).toEqual({
      objectKind: "InfraDevice",
      filters: [{ name: "any__value", value: "spine1" }],
    });
    await expect
      .poll(() => vi.mocked(getRelationships).mock.calls.at(-1)?.[0])
      .toMatchObject({ peer: "InfraDevice", search: "spine1" });
  });
});
