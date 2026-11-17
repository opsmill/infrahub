import { Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { cleanup } from "vitest-browser-react";

import { useGetArtifactFile } from "@/entities/artifacts/ui/queries/get-artifact-file.query";
import { AuthContext } from "@/entities/authentication/ui/auth-provider";
import type { ArtifactThread } from "@/entities/diff/domain/use-cases/get-artifact-content-diff";
import { ArtifactContentDiff } from "@/entities/diff/ui/artifact-diff/artifact-content-diff";
import { useGetArtifactContentDiff } from "@/entities/diff/ui/queries/get-artifact-content-diff.query";
import { useCreateObjectMutation } from "@/entities/nodes/object/ui/queries/create-object.mutation";
import { useDeleteObjectMutation } from "@/entities/nodes/object/ui/queries/delete-object.mutation";
import { useGetObjectPermissions } from "@/entities/permission/ui/queries/get-object-permissions.query";
import {
  PROPOSED_CHANGES_ARTIFACT_THREAD_OBJECT,
  PROPOSED_CHANGES_THREAD_COMMENT_OBJECT,
} from "@/entities/proposed-changes/domain/model/proposed-change-thread";

import { render } from "../../../../../tests/components/render";

vi.mock("@/entities/artifacts/ui/queries/get-artifact-file.query", () => ({
  useGetArtifactFile: vi.fn(),
}));

vi.mock("@/entities/diff/ui/queries/get-artifact-content-diff.query", () => ({
  useGetArtifactContentDiff: vi.fn(),
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
  "previous-storage": "line 1\nline 2\nline 3\n",
  "new-storage": "line 0\nline 1\nline 2\nline 3\n",
};

const generateThread = (storageId: string, lineNumber: number, text: string): ArtifactThread => ({
  id: `thread-${storageId}`,
  line_number: { value: lineNumber },
  storage_id: { value: storageId },
  comments: {
    edges: [{ node: { id: `comment-${storageId}`, text: { value: text } } }],
  },
});

const mockThreads = (threads: ArtifactThread[]) =>
  vi.mocked(useGetArtifactContentDiff).mockReturnValue({
    data: { threads },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  } as unknown as ReturnType<typeof useGetArtifactContentDiff>);

const mockMutations = ({ commentError }: { commentError?: Error } = {}) => {
  const create = vi.fn(
    async (
      { objectKind }: { objectKind: string },
      callbacks?: {
        onSuccess?: (data: { id: string }) => unknown;
        onError?: (error: Error) => unknown;
      }
    ) => {
      if (objectKind === PROPOSED_CHANGES_THREAD_COMMENT_OBJECT && commentError) {
        // Stops before the rejection, which the submit handler leaves unhandled.
        await callbacks?.onError?.(commentError);
        return;
      }

      await callbacks?.onSuccess?.({ id: "thread-1" });
      return { id: "thread-1" };
    }
  );
  const remove = vi.fn(async () => ({}));

  vi.mocked(useCreateObjectMutation).mockReturnValue({ mutateAsync: create } as never);
  vi.mocked(useDeleteObjectMutation).mockReturnValue({ mutateAsync: remove } as never);

  return { create, remove };
};

const renderArtifactDiff = () => {
  window.history.replaceState(null, "", "/proposed-changes/proposed-change-1/artifacts");

  return render(
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
          path="/proposed-changes/:proposedChangeId/artifacts"
          element={
            <ArtifactContentDiff
              id="artifact-1"
              itemPrevious={{ storage_id: "previous-storage" }}
              itemNew={{ storage_id: "new-storage" }}
            />
          }
        />
      </Routes>
    </AuthContext>
  );
};

const getLineRow = (component: Awaited<ReturnType<typeof render>>, text: string) => {
  const row = component.getByText(text, { exact: true }).first().element().closest("tr");
  if (!row) throw new Error(`Missing the diff row of "${text}"`);
  return row;
};

describe("ArtifactContentDiff", () => {
  beforeEach(() => {
    vi.mocked(useGetArtifactFile).mockImplementation(
      ({ storageId }) =>
        ({
          data: files[storageId],
          isLoading: false,
          error: null,
        }) as unknown as ReturnType<typeof useGetArtifactFile>
    );
    vi.mocked(useGetObjectPermissions).mockReturnValue({
      isPending: false,
      data: { create: { isAllowed: true } },
    } as never);
    mockThreads([]);
    mockMutations();
  });

  afterEach(async () => {
    await cleanup();
    window.history.replaceState(null, "", initialPath);
    vi.resetAllMocks();
    vi.restoreAllMocks();
  });

  test("labels each side with its storage id", async () => {
    // GIVEN
    mockThreads([]);

    // WHEN
    const component = await renderArtifactDiff();

    // THEN
    await expect.element(component.getByText("Storage id: previous-storage")).toBeVisible();
    await expect.element(component.getByText("Storage id: new-storage")).toBeVisible();
  });

  test.each([
    { storageId: "previous-storage", row: "line 2" },
    { storageId: "new-storage", row: "line 1" },
  ])(
    "shows a thread on $storageId under the line with its number on that side",
    async ({ storageId, row }) => {
      // GIVEN
      mockThreads([generateThread(storageId, 2, "Why this change?")]);

      // WHEN
      const component = await renderArtifactDiff();

      // THEN
      await expect.element(component.getByText("Why this change?")).toBeVisible();
      expect(getLineRow(component, row).nextElementSibling?.textContent).toContain(
        "Why this change?"
      );
    }
  );

  test("creates an artifact thread on the storage id of the commented side", async () => {
    // GIVEN
    const { create } = mockMutations();
    const component = await renderArtifactDiff();
    await component.getByText("line 0", { exact: true }).hover();
    await component.getByRole("button", { name: "Add a comment on line 1" }).click();
    await component.getByRole("textbox").fill("Why this change?");

    // WHEN
    await component.getByRole("button", { name: "Comment", exact: true }).click();

    // THEN
    await expect.element(component.getByRole("textbox")).not.toBeInTheDocument();
    expect(create).toHaveBeenNthCalledWith(
      1,
      {
        objectKind: PROPOSED_CHANGES_ARTIFACT_THREAD_OBJECT,
        data: {
          change: { id: "proposed-change-1" },
          resolved: { value: false },
          line_number: { value: 1 },
          storage_id: { value: "new-storage" },
          artifact_id: { value: "artifact-1" },
        },
      },
      expect.anything()
    );
  });

  test("deletes the artifact thread and shows an error when its first comment fails", async () => {
    // GIVEN
    const { remove } = mockMutations({ commentError: new Error("Comment rejected") });
    vi.spyOn(console, "error").mockImplementation(() => {});
    const component = await renderArtifactDiff();
    await component.getByText("line 0", { exact: true }).hover();
    await component.getByRole("button", { name: "Add a comment on line 1" }).click();
    await component.getByRole("textbox").fill("Why this change?");

    // WHEN
    await component.getByRole("button", { name: "Comment", exact: true }).click();

    // THEN
    await expect
      .element(component.getByText("An error occurred while creating the comment"))
      .toBeVisible();
    expect(remove).toHaveBeenCalledExactlyOnceWith({
      objectKind: PROPOSED_CHANGES_ARTIFACT_THREAD_OBJECT,
      objectId: "thread-1",
    });
  });
});
