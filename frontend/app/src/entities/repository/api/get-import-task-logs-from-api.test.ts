import { toast } from "react-toastify";
import { afterEach, describe, expect, it, vi } from "vitest";

import { getImportTaskLogsFromApi } from "./get-import-task-logs-from-api";

vi.mock("react-toastify", () => ({ toast: vi.fn() }));

describe("getImportTaskLogsFromApi", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("rejects a failed log fetch without showing the error toast", async () => {
    // GIVEN
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify({ data: null, errors: [{ message: "Log fetch failed" }] }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          })
        )
      )
    );

    // WHEN / THEN
    await expect(getImportTaskLogsFromApi({ taskId: "task-1", logLimit: 10 })).rejects.toThrow(
      "Log fetch failed"
    );
    expect(toast).not.toHaveBeenCalled();
  });
});
