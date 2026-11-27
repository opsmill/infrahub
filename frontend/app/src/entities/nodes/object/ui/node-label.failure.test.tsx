import { toast } from "react-toastify";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { NodeLabel } from "@/entities/nodes/object/ui/node-label";

import { render } from "../../../../../tests/components/render";

vi.mock("@/entities/branches/api/get-branches-from-api");
vi.mock("react-toastify", { spy: true });

const NODE_ID = "18a2e83c-0e80-fa90-3392-c51809fb54cf";

describe("NodeLabel when its request fails", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchSpy = vi.fn(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            data: null,
            errors: [{ message: "Branch: deleted-elsewhere not found." }],
          }),
          {
            status: 404,
            headers: { "Content-Type": "application/json" },
          }
        )
      )
    );
    vi.stubGlobal("fetch", fetchSpy);
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  test("shows the node id without alerting the user", async () => {
    // WHEN
    const component = await render(<NodeLabel id={NODE_ID} kind="CoreAccount" />);

    // THEN
    await expect.element(component.getByText(NODE_ID)).toBeVisible();
    expect(fetchSpy).toHaveBeenCalled();
    expect(toast).not.toHaveBeenCalled();
  });
});
