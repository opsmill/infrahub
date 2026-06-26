import { Provider } from "jotai";
import { createMemoryRouter, Navigate, RouterProvider } from "react-router";
import { afterEach, describe, expect, test } from "vitest";
import { render } from "vitest-browser-react";

import { Component as BranchDetailsLayout } from "@/pages/branches/details";

import { store } from "@/shared/stores";

import { branchesState } from "@/entities/branches/stores";
import { getBranchDetailsUrl } from "@/entities/branches/utils";

import { generateBranch } from "../../../tests/fake/branch";

// Mirrors the production branch routes in src/app/router.tsx: a single-segment
// `:branchName` route with an index tab child and a `*` catch-all that
// redirects unknown sub-paths back to the branch's index tab.
const renderBranchRoutes = (initialUrl: string) => {
  const router = createMemoryRouter(
    [
      {
        path: "/branches",
        children: [
          { index: true, element: <div>branches list</div> },
          {
            path: ":branchName",
            Component: BranchDetailsLayout,
            children: [
              { index: true, element: <div>branch index tab</div> },
              { path: "*", element: <Navigate to="." replace /> },
            ],
          },
        ],
      },
    ],
    { initialEntries: [initialUrl] }
  );

  return render(
    <Provider store={store}>
      <RouterProvider router={router} />
    </Provider>
  );
};

describe("Branch details navigation", () => {
  afterEach(() => {
    store.set(branchesState, []);
  });

  test("opens the branch detail page for a branch whose name contains a slash", async () => {
    // GIVEN
    const branch = generateBranch({ name: "feature/my-branch" });
    store.set(branchesState, [branch]);

    // WHEN
    const component = await renderBranchRoutes(getBranchDetailsUrl(branch.name));

    // THEN
    await expect
      .element(component.getByRole("heading", { name: "feature/my-branch" }))
      .toBeVisible();
  });
});
