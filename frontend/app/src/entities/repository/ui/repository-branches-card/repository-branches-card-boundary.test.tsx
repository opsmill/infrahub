import { describe, expect, test, vi } from "vitest";

import { RepositoryBranchesCardBoundary } from "@/entities/repository/ui/repository-branches-card/repository-branches-card-boundary";

import { render } from "../../../../../tests/components/render";

function Exploding(): never {
  throw new TypeError("Cannot read properties of null (reading 'color')");
}

describe("RepositoryBranchesCardBoundary", () => {
  test("renders what it wraps while nothing fails", async () => {
    // WHEN
    const component = await render(
      <RepositoryBranchesCardBoundary>
        <p>feature-auth</p>
      </RepositoryBranchesCardBoundary>
    );

    // THEN
    await expect.element(component.getByText("feature-auth", { exact: true })).toBeVisible();
  });

  test("holds a render failure inside the card instead of letting it escape", async () => {
    // GIVEN
    vi.spyOn(console, "error").mockImplementation(() => undefined);

    // WHEN
    const component = await render(
      <div>
        <h2>Repository details</h2>

        <RepositoryBranchesCardBoundary>
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

    vi.restoreAllMocks();
  });
});
