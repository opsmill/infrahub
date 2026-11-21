import type { ComponentProps } from "react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { page } from "vitest/browser";

import { AuthContext } from "@/entities/authentication/ui/auth-provider";
import { CommentableContentDiff } from "@/entities/diff/ui/content-diff/commentable-content-diff";
import type { DiffSide } from "@/entities/diff/ui/content-diff/line-comments";
import { useCreateObjectMutation } from "@/entities/nodes/object/ui/queries/create-object.mutation";
import { useDeleteObjectMutation } from "@/entities/nodes/object/ui/queries/delete-object.mutation";
import { useGetObjectPermissions } from "@/entities/permission/ui/queries/get-object-permissions.query";
import {
  PROPOSED_CHANGES_ARTIFACT_THREAD_OBJECT,
  PROPOSED_CHANGES_FILE_THREAD_OBJECT,
  PROPOSED_CHANGES_THREAD_COMMENT_OBJECT,
} from "@/entities/proposed-changes/domain/model/proposed-change-thread";

import { render } from "../../../../../tests/components/render";
import { initPointerTracking } from "../../../../../tests/components/utils";

vi.mock("@/entities/nodes/object/ui/queries/create-object.mutation", () => ({
  useCreateObjectMutation: vi.fn(),
}));

vi.mock("@/entities/nodes/object/ui/queries/delete-object.mutation", () => ({
  useDeleteObjectMutation: vi.fn(),
}));

vi.mock("@/entities/permission/ui/queries/get-object-permissions.query", () => ({
  useGetObjectPermissions: vi.fn(),
}));

const previousContent = "line 1\nline 2\nline 3\n";
const newContent = "line 1\nline 2 changed\nline 3\n";

interface TestThread {
  id: string;
  line_number: { value: number };
  side: DiffSide;
  comments: {
    edges: Array<{
      node: { id: string; text: { value: string } };
      node_metadata: { created_at: string; created_by: { display_label: string } };
    }>;
  };
}

const generateThread = (side: DiffSide, lineNumber: number, text: string): TestThread => ({
  id: `thread-${side}-${lineNumber}`,
  line_number: { value: lineNumber },
  side,
  comments: {
    edges: [
      {
        node: { id: `comment-${side}-${lineNumber}`, text: { value: text } },
        node_metadata: {
          created_at: "2024-01-01T00:00:00Z",
          created_by: { display_label: "Admin" },
        },
      },
    ],
  },
});

const signedIn = {
  accessToken: "token",
  isAuthenticated: true,
  setToken: () => {},
  user: { id: "user-1" },
};

type Props = ComponentProps<typeof CommentableContentDiff<TestThread>>;

const renderDiff = (props: Partial<Props> = {}, { isAuthenticated = true } = {}) =>
  render(
    <AuthContext value={{ ...signedIn, isAuthenticated }}>
      <CommentableContentDiff<TestThread>
        previousContent={previousContent}
        newContent={newContent}
        proposedChangeId="proposed-change-1"
        threads={[]}
        onThreadsChange={() => {}}
        isThreadOnSide={(thread, side) => thread.side === side}
        threadKind={PROPOSED_CHANGES_FILE_THREAD_OBJECT}
        buildThreadData={({ side }) => ({ commit: { value: `${side}-commit` } })}
        {...props}
      />
    </AuthContext>
  );

interface MutateCallbacks {
  onSuccess?: (data: { id: string }) => unknown;
  onError?: (error: Error) => unknown;
}

const mockMutations = ({ commentError }: { commentError?: Error } = {}) => {
  const create = vi.fn(
    async ({ objectKind }: { objectKind: string }, callbacks?: MutateCallbacks) => {
      if (objectKind === PROPOSED_CHANGES_THREAD_COMMENT_OBJECT && commentError) {
        // Stops before the rejection, which the submit handler leaves unhandled.
        await callbacks?.onError?.(commentError);
        return;
      }

      const created = {
        id: objectKind === PROPOSED_CHANGES_THREAD_COMMENT_OBJECT ? "comment-1" : "thread-1",
      };
      await callbacks?.onSuccess?.(created);
      return created;
    }
  );
  const remove = vi.fn(async () => ({}));

  vi.mocked(useCreateObjectMutation).mockReturnValue({ mutateAsync: create } as never);
  vi.mocked(useDeleteObjectMutation).mockReturnValue({ mutateAsync: remove } as never);

  return { create, remove };
};

const getLineRow = (component: Awaited<ReturnType<typeof render>>, text: string) => {
  const row = component.getByText(text, { exact: true }).first().element().closest("tr");
  if (!row) throw new Error(`Missing the diff row of "${text}"`);
  return row;
};

describe("CommentableContentDiff", () => {
  beforeEach(() => {
    mockMutations();
    vi.mocked(useGetObjectPermissions).mockReturnValue({
      isPending: false,
      data: { create: { isAllowed: true } },
    } as never);
  });

  afterEach(async () => {
    // The pointer position carries over between tests in browser mode.
    await initPointerTracking(page.elementLocator(document.body));
    vi.resetAllMocks();
    vi.restoreAllMocks();
  });

  test("renders the label of each side above the diff", async () => {
    // GIVEN
    const labels = { previousLabel: "Commit: 1a2b3c", newLabel: "Commit: 4d5e6f" };

    // WHEN
    const component = await renderDiff(labels);

    // THEN
    await expect.element(component.getByText("Commit: 1a2b3c")).toBeVisible();
    await expect.element(component.getByText("Commit: 4d5e6f")).toBeVisible();
  });

  test.each([
    { side: "old", row: "line 2" },
    { side: "new", row: "line 1" },
  ] as const)(
    "shows a thread on the $side side under the line with its number on that side",
    async ({ side, row }) => {
      // GIVEN
      const threads = [generateThread(side, 2, "Why this change?")];

      // WHEN
      const component = await renderDiff({
        previousContent,
        newContent: `line 0\n${previousContent}`,
        threads,
      });

      // THEN
      await expect.element(component.getByText("Why this change?")).toBeVisible();
      expect(getLineRow(component, row).nextElementSibling?.textContent).toContain(
        "Why this change?"
      );
    }
  );

  test("shows the add-comment button when a signed-in user hovers a line of a proposed change", async () => {
    // GIVEN
    const component = await renderDiff();

    // WHEN
    await component.getByText("line 2 changed", { exact: true }).hover();

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Add a comment on line 2" }))
      .toBeVisible();
  });

  test.each([
    { name: "the user is not signed in", props: {}, isAuthenticated: false },
    {
      name: "the diff is not in a proposed change",
      props: { proposedChangeId: undefined },
      isAuthenticated: true,
    },
    {
      name: "the line has a thread",
      props: { threads: [generateThread("new", 2, "Why this change?")] },
      isAuthenticated: true,
    },
  ])("hides the add-comment button when $name", async ({ props, isAuthenticated }) => {
    // GIVEN
    const component = await renderDiff(props, { isAuthenticated });

    // WHEN
    await component.getByText("line 2 changed", { exact: true }).hover();

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Add a comment on line 2" }))
      .not.toBeInTheDocument();
  });

  test("opens the comment form under the line when its add-comment button is clicked", async () => {
    // GIVEN
    const component = await renderDiff();
    await component.getByText("line 2 changed", { exact: true }).hover();

    // WHEN
    await component.getByRole("button", { name: "Add a comment on line 2" }).click();

    // THEN
    await expect.element(component.getByRole("textbox")).toBeVisible();
    expect(getLineRow(component, "line 2 changed").nextElementSibling?.textContent).toContain(
      "Add a comment"
    );
  });

  test("closes the comment form on cancel", async () => {
    // GIVEN
    const component = await renderDiff();
    await component.getByText("line 2 changed", { exact: true }).hover();
    await component.getByRole("button", { name: "Add a comment on line 2" }).click();

    // WHEN
    await component.getByRole("button", { name: "Cancel" }).click();

    // THEN
    await expect.element(component.getByRole("textbox")).not.toBeInTheDocument();
  });

  test("creates a thread of the given kind with the caller's data, then its first comment", async () => {
    // GIVEN
    const { create } = mockMutations();
    const onThreadsChange = vi.fn();
    const component = await renderDiff({
      onThreadsChange,
      threadKind: PROPOSED_CHANGES_FILE_THREAD_OBJECT,
      buildThreadData: ({ side, lineNumber }) => ({
        commit: { value: `${side}-commit` },
        label: { value: `line ${lineNumber}` },
      }),
    });
    await component.getByText("line 2 changed", { exact: true }).hover();
    await component.getByRole("button", { name: "Add a comment on line 2" }).click();
    await component.getByRole("textbox").fill("Why this change?");

    // WHEN
    await component.getByRole("button", { name: "Comment", exact: true }).click();

    // THEN
    await expect.element(component.getByRole("textbox")).not.toBeInTheDocument();
    expect(create.mock.calls.map(([params]) => params)).toEqual([
      {
        objectKind: PROPOSED_CHANGES_FILE_THREAD_OBJECT,
        data: {
          change: { id: "proposed-change-1" },
          resolved: { value: false },
          line_number: { value: 2 },
          commit: { value: "new-commit" },
          label: { value: "line 2" },
        },
      },
      {
        objectKind: PROPOSED_CHANGES_THREAD_COMMENT_OBJECT,
        data: { text: { value: "Why this change?" }, thread: { id: "thread-1" } },
      },
    ]);
    expect(onThreadsChange).toHaveBeenCalledOnce();
  });

  test("deletes the thread with its own kind and shows an error when the comment fails", async () => {
    // GIVEN
    const { remove } = mockMutations({ commentError: new Error("Comment rejected") });
    vi.spyOn(console, "error").mockImplementation(() => {});
    const component = await renderDiff({ threadKind: PROPOSED_CHANGES_ARTIFACT_THREAD_OBJECT });
    await component.getByText("line 2", { exact: true }).hover();
    await component.getByRole("button", { name: "Add a comment on line 2" }).click();
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
