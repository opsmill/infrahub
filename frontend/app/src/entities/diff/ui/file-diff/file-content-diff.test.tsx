import { Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { page } from "vitest/browser";
import { cleanup } from "vitest-browser-react";

import { AuthContext } from "@/entities/authentication/ui/auth-provider";
import type { FileThread } from "@/entities/diff/domain/use-cases/get-file-content-diff";
import { FileContentDiff } from "@/entities/diff/ui/file-diff/file-content-diff";
import { useGetFile } from "@/entities/diff/ui/queries/get-file.query";
import { useGetFileContentDiff } from "@/entities/diff/ui/queries/get-file-content-diff.query";
import { useCreateObjectMutation } from "@/entities/nodes/object/ui/queries/create-object.mutation";
import { useDeleteObjectMutation } from "@/entities/nodes/object/ui/queries/delete-object.mutation";
import { useGetObjectPermissions } from "@/entities/permission/ui/queries/get-object-permissions.query";
import { PROPOSED_CHANGES_FILE_THREAD_OBJECT } from "@/entities/proposed-changes/domain/model/proposed-change-thread";

import { render } from "../../../../../tests/components/render";
import { initPointerTracking } from "../../../../../tests/components/utils";

vi.mock("@/entities/diff/ui/queries/get-file.query", () => ({
  useGetFile: vi.fn(),
}));

vi.mock("@/entities/diff/ui/queries/get-file-content-diff.query", () => ({
  useGetFileContentDiff: vi.fn(),
}));

vi.mock("@/entities/nodes/object/ui/queries/create-object.mutation", () => ({
  useCreateObjectMutation: vi.fn(),
}));

vi.mock("@/entities/nodes/object/ui/queries/delete-object.mutation", () => ({
  useDeleteObjectMutation: vi.fn(),
}));

vi.mock("@/entities/permission/ui/queries/get-object-permissions.query", () => ({
  useGetObjectPermissions: vi.fn(),
}));

const initialPath = window.location.pathname;

const files: Record<string, string> = {
  "commit-from": "line 1\nline 2\nline 3\n",
  "commit-to": "line 0\nline 1\nline 2\nline 3\n",
};

const generateThread = (commit: string, lineNumber: number, text: string): FileThread => ({
  id: `thread-${commit}`,
  line_number: { value: lineNumber },
  commit: { value: commit },
  comments: {
    edges: [{ node: { id: `comment-${commit}`, text: { value: text } } }],
  },
});

const mockThreads = (threads: FileThread[]) =>
  vi.mocked(useGetFileContentDiff).mockReturnValue({
    data: { threads },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  } as unknown as ReturnType<typeof useGetFileContentDiff>);

const renderFileDiff = async () => {
  window.history.replaceState(null, "", "/proposed-changes/proposed-change-1/files");

  const component = await render(
    <AuthContext
      value={{
        accessToken: "token",
        isAuthenticated: true,
        setToken: () => {},
        user: { id: "user-1" },
      }}
    >
      <Routes>
        <Route
          path="/proposed-changes/:proposedChangeId/files"
          element={
            <FileContentDiff
              repositoryId="repository-1"
              repositoryDisplayName="infra-repo"
              file={{ branch: "feature", location: "configs/router.cfg", action: "updated" }}
              commitFrom="commit-from"
              commitTo="commit-to"
            />
          }
        />
      </Routes>
    </AuthContext>
  );
  await component.getByText("configs/router.cfg").click();

  return component;
};

const getLineRow = (component: Awaited<ReturnType<typeof render>>, text: string) => {
  const row = component.getByText(text, { exact: true }).first().element().closest("tr");
  if (!row) throw new Error(`Missing the diff row of "${text}"`);
  return row;
};

describe("FileContentDiff", () => {
  beforeEach(() => {
    vi.mocked(useGetFile).mockImplementation(
      ({ commit }) =>
        ({
          data: files[commit ?? ""],
          isPending: false,
          error: null,
        }) as unknown as ReturnType<typeof useGetFile>
    );
    vi.mocked(useGetObjectPermissions).mockReturnValue({
      isPending: false,
      data: { create: { isAllowed: true } },
    } as never);
    mockThreads([]);
  });

  afterEach(async () => {
    // The pointer position carries over between tests in browser mode.
    await initPointerTracking(page.elementLocator(document.body));
    await cleanup();
    window.history.replaceState(null, "", initialPath);
    vi.resetAllMocks();
  });

  test("labels each side of the opened file with its commit", async () => {
    // GIVEN
    mockThreads([]);

    // WHEN
    const component = await renderFileDiff();

    // THEN
    await expect.element(component.getByText("Commit: commit-from")).toBeVisible();
    await expect.element(component.getByText("Commit: commit-to")).toBeVisible();
  });

  test("shows a thread on the source commit under the line with its old number", async () => {
    // GIVEN
    mockThreads([generateThread("commit-from", 2, "Why this change?")]);

    // WHEN
    const component = await renderFileDiff();

    // THEN
    await expect.element(component.getByText("Why this change?")).toBeVisible();
    expect(getLineRow(component, "line 2").nextElementSibling?.textContent).toContain(
      "Why this change?"
    );
  });

  test("shows a thread on the target commit under the line with its new number", async () => {
    // GIVEN
    mockThreads([generateThread("commit-to", 4, "Why this change?")]);

    // WHEN
    const component = await renderFileDiff();

    // THEN
    await expect.element(component.getByText("Why this change?")).toBeVisible();
    expect(getLineRow(component, "line 3").nextElementSibling?.textContent).toContain(
      "Why this change?"
    );
  });

  test.each([
    { side: "new", line: "line 0", commit: "commit-to" },
    { side: "old", line: "line 1", commit: "commit-from" },
  ])(
    "creates a file thread on $commit when commenting on the $side side",
    async ({ line, commit }) => {
      // GIVEN
      const create = vi.fn(
        async (_params: unknown, callbacks?: { onSuccess?: (data: { id: string }) => unknown }) => {
          await callbacks?.onSuccess?.({ id: "thread-1" });
          return { id: "thread-1" };
        }
      );
      vi.mocked(useCreateObjectMutation).mockReturnValue({ mutateAsync: create } as never);
      vi.mocked(useDeleteObjectMutation).mockReturnValue({ mutateAsync: vi.fn() } as never);
      const component = await renderFileDiff();
      await component.getByText(line, { exact: true }).first().hover();
      await component.getByRole("button", { name: "Add a comment on line 1" }).click();
      await component.getByRole("textbox").fill("Why this change?");

      // WHEN
      await component.getByRole("button", { name: "Comment", exact: true }).click();

      // THEN
      await expect.element(component.getByRole("textbox")).not.toBeInTheDocument();
      expect(create).toHaveBeenNthCalledWith(
        1,
        {
          objectKind: PROPOSED_CHANGES_FILE_THREAD_OBJECT,
          data: {
            change: { id: "proposed-change-1" },
            resolved: { value: false },
            line_number: { value: 1 },
            label: { value: "infra-repo - configs/router.cfg:1" },
            commit: { value: commit },
            file: { value: "configs/router.cfg" },
            repository: { id: "repository-1" },
          },
        },
        expect.anything()
      );
    }
  );
});
