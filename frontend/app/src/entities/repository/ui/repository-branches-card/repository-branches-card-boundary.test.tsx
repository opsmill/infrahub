import { afterEach, describe, expect, it, vi } from "vitest";

import { RepositoryBranchesCardBoundary } from "@/entities/repository/ui/repository-branches-card/repository-branches-card-boundary";

import { render } from "../../../../../tests/components/render";

function Exploding(): never {
  throw new TypeError("Cannot read properties of null (reading 'color')");
}

describe("RepositoryBranchesCardBoundary", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders what it wraps while nothing fails", async () => {
    // WHEN
    const component = await render(
      <RepositoryBranchesCardBoundary resetKeys={["repo-1", 1]}>
        <p>feature-auth</p>
      </RepositoryBranchesCardBoundary>
    );

    // THEN
    await expect.element(component.getByText("feature-auth", { exact: true })).toBeVisible();
  });

  it("holds a render failure inside the card instead of letting it escape", async () => {
    // GIVEN
    vi.spyOn(console, "error").mockImplementation(() => undefined);

    // WHEN
    const component = await render(
      <div>
        <h2>Repository details</h2>

        <RepositoryBranchesCardBoundary resetKeys={["repo-1", 1]}>
          <Exploding />
        </RepositoryBranchesCardBoundary>
      </div>
    );

    // THEN
    await expect
      .element(component.getByText("The branches could not be loaded", { exact: true }))
      .toBeVisible();
    await expect
      .element(component.getByRole("heading", { name: "Repository details" }))
      .toBeVisible();
  });

  it("shows the next page of branches once the query inputs move on", async () => {
    // GIVEN a card left in its failed state by a row that threw
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    const component = await render(
      <RepositoryBranchesCardBoundary resetKeys={["repo-1", 1]}>
        <Exploding />
      </RepositoryBranchesCardBoundary>
    );
    await expect
      .element(component.getByText("The branches could not be loaded", { exact: true }))
      .toBeVisible();

    // WHEN the page changes and the new row set renders
    await component.rerender(
      <RepositoryBranchesCardBoundary resetKeys={["repo-1", 2]}>
        <p>release-2-0</p>
      </RepositoryBranchesCardBoundary>
    );

    // THEN
    await expect.element(component.getByText("release-2-0", { exact: true })).toBeVisible();
    expect(
      component.getByText("The branches could not be loaded", { exact: true }).elements()
    ).toHaveLength(0);
  });
});
