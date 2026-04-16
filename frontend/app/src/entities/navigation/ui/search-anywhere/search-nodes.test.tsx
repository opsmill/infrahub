import { describe, expect, test, vi } from "vitest";

import { render } from "../../../../../tests/components/render";
import { NodesOptions } from "./search-nodes";

vi.mock("@/entities/schema/ui/hooks/useSchema");
vi.mock("@/entities/nodes/object/domain/get-object.query");

import { useGetObject } from "@/entities/nodes/object/domain/get-object.query";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

describe("NodesOptions", () => {
  test("does not fetch object details when schema is not found", async () => {
    // GIVEN - schema not found (e.g., SchemaNode kind not in the frontend registry)
    vi.mocked(useSchema).mockReturnValue({
      schema: null,
      isGeneric: false,
      isNode: false,
      isProfile: false,
      isTemplate: false,
    });

    // WHEN
    await render(
      <NodesOptions node={{ id: "17f1f99f-0e72-f5bf-367e-c51a42a1f971", kind: "SchemaNode" }} />
    );

    // THEN - useGetObject should never be called since schema is null
    expect(useGetObject).not.toHaveBeenCalled();
  });
});
