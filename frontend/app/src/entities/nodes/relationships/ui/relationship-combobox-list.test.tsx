import { describe, expect, test, vi } from "vitest";

import { render } from "../../../../../tests/components/render";
import { RelationshipComboboxList } from "./relationship-combobox-list";

const useRelationshipsMock = vi.fn();
const useSchemaMock = vi.fn();

vi.mock("@/entities/nodes/relationships/ui/queries/get-relationships.query", () => ({
  useRelationships: (args: unknown) => useRelationshipsMock(args),
}));
vi.mock("@/entities/schema/ui/hooks/useSchema", () => ({
  useSchema: () => useSchemaMock(),
}));
vi.mock("@/shared/utils/common", () => ({
  classNames: (...args: unknown[]) => args.filter(Boolean).join(" "),
  debounce: (fn: (...args: unknown[]) => unknown) => fn,
}));

function setupReturn() {
  return {
    isPending: false,
    data: { pages: [[]] },
    error: null,
    fetchNextPage: vi.fn(),
    hasNextPage: false,
    isFetchingNextPage: false,
  };
}

describe("RelationshipComboboxList", () => {
  test("uses the search filter for non-UUID queries", async () => {
    useRelationshipsMock.mockReturnValue(setupReturn());
    useSchemaMock.mockReturnValue({ schema: { label: "Device" } });

    const component = await render(
      <RelationshipComboboxList peer="InfraDevice" onSelect={vi.fn()} />
    );

    // Clear previous calls from initial render
    useRelationshipsMock.mockClear();

    // Find and type in the cmdk input
    const input = component.getByRole("combobox");
    await input.click();
    await input.fill("router-1");

    // Wait for debounce
    await new Promise((resolve) => setTimeout(resolve, 350));

    const lastCall = useRelationshipsMock.mock.calls.at(-1)?.[0];
    expect(lastCall).toEqual({
      peer: "InfraDevice",
      search: "router-1",
      filterQuery: undefined,
    });
  });

  test("switches to ids filter when search is a UUID", async () => {
    useRelationshipsMock.mockReturnValue(setupReturn());
    useSchemaMock.mockReturnValue({ schema: { label: "Device" } });

    const component = await render(
      <RelationshipComboboxList peer="InfraDevice" onSelect={vi.fn()} />
    );

    // Clear previous calls from initial render
    useRelationshipsMock.mockClear();

    const input = component.getByRole("combobox");
    await input.click();
    await input.fill("17a4cdef-1234-4abc-8def-0123456789ab");

    await new Promise((resolve) => setTimeout(resolve, 350));

    const lastCall = useRelationshipsMock.mock.calls.at(-1)?.[0];
    expect(lastCall).toEqual({
      peer: "InfraDevice",
      search: undefined,
      filterQuery: { ids: ["17a4cdef-1234-4abc-8def-0123456789ab"] },
    });
  });

  test("UUID match overrides a caller-provided filterQuery", async () => {
    useRelationshipsMock.mockReturnValue(setupReturn());
    useSchemaMock.mockReturnValue({ schema: { label: "Device" } });

    const component = await render(
      <RelationshipComboboxList
        peer="InfraDevice"
        onSelect={vi.fn()}
        filterQuery={{ parent__ids: ["zzz"] }}
      />
    );

    // Clear previous calls from initial render
    useRelationshipsMock.mockClear();

    const input = component.getByRole("combobox");
    await input.click();
    await input.fill("17a4cdef-1234-4abc-8def-0123456789ab");

    await new Promise((resolve) => setTimeout(resolve, 350));

    const lastCall = useRelationshipsMock.mock.calls.at(-1)?.[0];
    expect(lastCall.filterQuery).toEqual({ ids: ["17a4cdef-1234-4abc-8def-0123456789ab"] });
  });
});
