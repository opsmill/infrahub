import { afterEach, describe, expect, test, vi } from "vitest";

import { useGetCheckDetails } from "@/entities/diff/ui/queries/get-check-details.query";

import { render } from "../../../../../tests/components/render";
import { Check } from "./check";

vi.mock("@/entities/diff/ui/queries/get-check-details.query");

const SKIPPED_MESSAGE =
  "Not rendered: one run of the query cabling_plan_logical is estimated at 991,262 worst-case database rows for this target, and the limit is 250,000. Infrahub generates this artifact after the merge.";

const mockCheckDetails = (conclusion: string, severity: string) => {
  vi.mocked(useGetCheckDetails).mockReturnValue({
    isPending: false,
    error: null,
    data: {
      __typename: "CoreArtifactCheck",
      display_label: "cabling_plan: dc1",
      name: { value: "cabling_plan: dc1" },
      kind: { value: "ArtifactDefinition" },
      origin: { value: "repository-1" },
      created_at: { value: "2026-10-11T10:00:00Z" },
      message: { value: SKIPPED_MESSAGE },
      severity: { value: severity },
      conclusion: { value: conclusion },
      conflicts: null,
    },
  } as unknown as ReturnType<typeof useGetCheckDetails>);
};

describe("Check", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  test("shows the skipped icon for a skipped check", async () => {
    // GIVEN
    mockCheckDetails("skipped", "info");
    const component = await render(<Check id="check-1" />);
    const icon = component.getByTestId("check-skipped").element() as HTMLElement;

    // WHEN
    icon.focus();

    // THEN
    await expect.element(component.getByRole("tooltip", { name: "Skipped" })).toBeVisible();
  });

  test("does not show the skipped icon for a successful check", async () => {
    // GIVEN
    mockCheckDetails("success", "success");

    // WHEN
    const component = await render(<Check id="check-1" />);

    // THEN
    await expect.element(component.getByText("cabling_plan: dc1")).toBeVisible();
    expect(component.getByTestId("check-skipped").query()).toBeNull();
  });
});
