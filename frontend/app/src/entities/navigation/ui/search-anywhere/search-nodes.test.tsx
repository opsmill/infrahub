import { beforeEach, describe, expect, test, vi } from "vitest";

import { useGetSearchAnywhere } from "@/entities/navigation/domain/search-anywhere.query";
import { useGetObject } from "@/entities/nodes/object/domain/get-object.query";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

import { render } from "../../../../../tests/components/render";
import { generateNodeSchema } from "../../../../../tests/fake/schema";
import { SearchNodes } from "./search-nodes";

vi.mock("@/entities/schema/ui/hooks/useSchema");
vi.mock("@/entities/navigation/domain/search-anywhere.query");
vi.mock("@/entities/nodes/object/domain/get-object.query");
vi.mock("cmdk", () => ({
  Command: {
    Item: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <div {...props}>{children}</div>
    ),
    Group: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <div {...props}>{children}</div>
    ),
  },
  useCommandState: () => "test-uuid-1234",
}));
vi.mock("@/entities/navigation/ui/search-anywhere/search-anywhere-context", () => ({
  useSearchAnywhereContext: () => ({ closeDialog: vi.fn() }),
}));
vi.mock("react-router", async () => {
  const actual = await vi.importActual("react-router");
  return { ...actual, useNavigate: () => vi.fn() };
});
vi.mock("@/entities/nodes/object-items/getSchemaObjectColumns", () => ({
  getSchemaObjectColumns: () => [],
}));

const useGetSearchAnywhereMock = vi.mocked(useGetSearchAnywhere);
const useSchemaMock = vi.mocked(useSchema);
const useGetObjectMock = vi.mocked(useGetObject);

describe("SearchNodes - Schema/Internal node rendering", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("renders simplified view for Schema namespace node with display_label", async () => {
    // GIVEN
    useGetSearchAnywhereMock.mockReturnValue({
      data: {
        count: 1,
        matchingObjects: [{ id: "uuid-1", kind: "SchemaNode", display_label: "InfraDevice" }],
      },
      isPending: false,
      error: null,
    } as ReturnType<typeof useGetSearchAnywhere>);

    useSchemaMock.mockReturnValue({ schema: null } as ReturnType<typeof useSchema>);

    // WHEN
    const component = await render(<SearchNodes />);

    // THEN
    await expect.element(component.getByText("InfraDevice")).toBeVisible();
    await expect.element(component.getByText("Schema", { exact: true })).toBeVisible();
    await expect.element(component.getByText("SchemaNode", { exact: true })).toBeVisible();
  });

  test("renders kind as fallback when display_label is missing", async () => {
    // GIVEN
    useGetSearchAnywhereMock.mockReturnValue({
      data: {
        count: 1,
        matchingObjects: [{ id: "uuid-2", kind: "InternalWidget", display_label: null }],
      },
      isPending: false,
      error: null,
    } as ReturnType<typeof useGetSearchAnywhere>);

    useSchemaMock.mockReturnValue({ schema: null } as ReturnType<typeof useSchema>);

    // WHEN
    const component = await render(<SearchNodes />);

    // THEN - label falls back to kind, which also appears in the kind badge
    await expect.element(component.getByText("InternalWidget").first()).toBeVisible();
    await expect.element(component.getByText("Schema", { exact: true })).toBeVisible();
  });

  test("renders full detail view for regular node", async () => {
    // GIVEN
    const mockSchema = generateNodeSchema({
      kind: "InfraDevice",
      namespace: "Infra",
      label: "Device",
    });

    useGetSearchAnywhereMock.mockReturnValue({
      data: {
        count: 1,
        matchingObjects: [{ id: "uuid-3", kind: "InfraDevice", display_label: "device-01" }],
      },
      isPending: false,
      error: null,
    } as ReturnType<typeof useGetSearchAnywhere>);

    useSchemaMock.mockReturnValue({ schema: mockSchema } as ReturnType<typeof useSchema>);

    useGetObjectMock.mockReturnValue({
      data: {
        id: "uuid-3",
        __typename: "InfraDevice",
        display_label: "device-01",
      },
      isPending: false,
      error: null,
    } as ReturnType<typeof useGetObject>);

    // WHEN
    const component = await render(<SearchNodes />);

    // THEN
    await expect.element(component.getByText("Infra")).toBeVisible();
    await expect.element(component.getByText("Device")).toBeVisible();
  });
});
