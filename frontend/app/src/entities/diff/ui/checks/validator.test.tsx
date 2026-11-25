import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { getArtifactValidatorDetailsFromApi } from "@/entities/diff/api/get-artifact-validator-details-from-api";
import { getCheckDetailsFromApi } from "@/entities/diff/api/get-check-details-from-api";
import { getValidatorDetailsFromApi } from "@/entities/diff/api/get-validator-details-from-api";

import { render } from "../../../../../tests/components/render";
import {
  generateArtifactCheck,
  generateArtifactValidator,
  generateArtifactValidatorDetails,
} from "../../../../../tests/fake/check";
import { Validator } from "./validator";

vi.mock("@/entities/diff/api/get-artifact-validator-details-from-api");
vi.mock("@/entities/diff/api/get-check-details-from-api");
vi.mock("@/entities/diff/api/get-validator-details-from-api");

const artifactApi = vi.mocked(getArtifactValidatorDetailsFromApi);
const genericApi = vi.mocked(getValidatorDetailsFromApi);
const checkApi = vi.mocked(getCheckDetailsFromApi);

beforeEach(() => {
  artifactApi.mockImplementation(async ({ ids, checksOffset, checksFailedFirst }) => {
    const validatorId = ids?.[0] ?? "artifact-validator";
    const checkIds = checksOffset
      ? [`${validatorId}-next-page`]
      : checksFailedFirst
        ? [`${validatorId}-failed-z`, `${validatorId}-success-a`]
        : [`${validatorId}-success-a`, `${validatorId}-failed-z`];
    return generateArtifactValidatorDetails({ validatorId, checkIds, count: 30 });
  });
  genericApi.mockResolvedValue({ data: { CoreValidator: { edges: [] } } });
  checkApi.mockImplementation(async ({ id }) => ({
    data: {
      CoreCheck: {
        edges: [
          {
            node: generateArtifactCheck({ id, name: { value: id } }),
          },
        ],
      },
    },
  }));
});

afterEach(() => {
  vi.resetAllMocks();
  window.history.replaceState(null, "", window.location.pathname);
});

describe("artifact validator check ordering", () => {
  test("requests failed first by default and displays the server's card order", async () => {
    // GIVEN
    const validator = generateArtifactValidator();
    const component = await render(<Validator validator={validator} />);

    // WHEN
    await component.getByText(validator.display_label!).click();

    // THEN
    await expect.element(component.getByRole("checkbox", { name: "Failed first" })).toBeChecked();
    await expect.element(component.getByText("artifact-validator-failed-z")).toBeVisible();
    await expect.element(component.getByText("artifact-validator-success-a")).toBeVisible();
    expect(
      component
        .getByText("artifact-validator-failed-z")
        .element()
        .compareDocumentPosition(component.getByText("artifact-validator-success-a").element())
    ).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(artifactApi).toHaveBeenCalledWith({
      ids: [validator.id],
      checksOffset: 0,
      checksLimit: 10,
      checksFailedFirst: true,
    });
    expect(genericApi).not.toHaveBeenCalled();
  });

  test("turning failed first off resets only that artifact's page and restores server order", async () => {
    // GIVEN
    const validator = generateArtifactValidator();
    const params = new URLSearchParams({
      "artifact-checks-artifact-validator": JSON.stringify({ limit: 10, offset: 10 }),
      "artifact-checks-other-validator": JSON.stringify({ limit: 20, offset: 20 }),
      pagination: JSON.stringify({ limit: 50, offset: 50 }),
    });
    window.history.replaceState(null, "", `?${params}`);
    const component = await render(<Validator validator={validator} />);
    await component.getByText(validator.display_label!).click();
    await expect.element(component.getByText("artifact-validator-next-page")).toBeVisible();

    // WHEN
    await component.getByText("Failed first", { exact: true }).click();

    // THEN
    await expect.element(component.getByText("artifact-validator-success-a")).toBeVisible();
    await expect.element(component.getByText("artifact-validator-failed-z")).toBeVisible();
    expect(
      component
        .getByText("artifact-validator-success-a")
        .element()
        .compareDocumentPosition(component.getByText("artifact-validator-failed-z").element())
    ).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(artifactApi).toHaveBeenLastCalledWith({
      ids: [validator.id],
      checksOffset: 0,
      checksLimit: 10,
      checksFailedFirst: false,
    });
    await expect
      .element(component.getByRole("button", { name: /Page 1/ }))
      .toHaveAttribute("aria-current", "page");
    const updatedParams = new URLSearchParams(window.location.search);
    expect(updatedParams.get("artifact-checks-other-validator")).toBe(
      params.get("artifact-checks-other-validator")
    );
    expect(updatedParams.get("pagination")).toBe(params.get("pagination"));
  });

  test("keeps the selected order after closing and reopening the artifact section", async () => {
    // GIVEN
    const validator = generateArtifactValidator();
    const component = await render(<Validator validator={validator} />);
    await component.getByText(validator.display_label!).click();
    await component.getByText("Failed first", { exact: true }).click();
    await expect
      .element(component.getByRole("checkbox", { name: "Failed first" }))
      .not.toBeChecked();

    // WHEN
    await component.getByText(validator.display_label!).click();
    await component.getByText(validator.display_label!).click();

    // THEN
    await expect
      .element(component.getByRole("checkbox", { name: "Failed first" }))
      .not.toBeChecked();
    await expect.element(component.getByText("artifact-validator-success-a")).toBeVisible();
  });

  test("changing one artifact's order leaves another artifact's control and page unchanged", async () => {
    // GIVEN
    const first = generateArtifactValidator();
    const second = generateArtifactValidator({
      id: "second",
      display_label: "Artifact Validator: Other",
    });
    window.history.replaceState(
      null,
      "",
      `?${new URLSearchParams({
        "artifact-checks-second": JSON.stringify({ limit: 10, offset: 10 }),
      })}`
    );
    const component = await render(
      <>
        <section aria-label="First artifact">
          <Validator validator={first} />
        </section>
        <section aria-label="Second artifact">
          <Validator validator={second} />
        </section>
      </>
    );
    await component.getByText(first.display_label!).click();
    await component.getByText(second.display_label!).click();
    await expect.element(component.getByText("second-next-page")).toBeVisible();
    const secondCallsBefore = artifactApi.mock.calls.filter(
      ([params]) => params.ids?.[0] === "second"
    ).length;

    // WHEN
    await component
      .getByRole("region", { name: "First artifact" })
      .getByText("Failed first", { exact: true })
      .click();

    // THEN
    await expect.element(component.getByText("artifact-validator-success-a")).toBeVisible();
    await expect
      .element(
        component
          .getByRole("region", { name: "Second artifact" })
          .getByRole("checkbox", { name: "Failed first" })
      )
      .toBeChecked();
    await expect.element(component.getByText("second-next-page")).toBeVisible();
    expect(artifactApi.mock.calls.filter(([params]) => params.ids?.[0] === "second")).toHaveLength(
      secondCallsBefore
    );
  });

  test("keeps the existing page-size choices while failed first is selected", async () => {
    // GIVEN
    const validator = generateArtifactValidator();
    const component = await render(<Validator validator={validator} />);
    await component.getByText(validator.display_label!).click();
    await component.getByRole("combobox").click();

    // WHEN
    await component.getByRole("option", { name: "20", exact: true }).click();

    // THEN
    await expect.element(component.getByRole("combobox")).toBeVisible();
    expect(artifactApi).toHaveBeenLastCalledWith({
      ids: [validator.id],
      checksOffset: 0,
      checksLimit: 20,
      checksFailedFirst: true,
    });
  });

  test("leaves non-artifact validators on their existing query and pagination", async () => {
    // GIVEN
    const validator = {
      ...generateArtifactValidator(),
      __typename: "CoreDataValidator",
      display_label: "Data Integrity",
    };
    window.history.replaceState(
      null,
      "",
      `?${new URLSearchParams({
        pagination: JSON.stringify({ limit: 20, offset: 20 }),
      })}`
    );
    const component = await render(<Validator validator={validator} />);

    // WHEN
    await component.getByText("Data Integrity").click();

    // THEN
    await expect.element(component.getByText("No checks found.")).toBeVisible();
    expect(component.getByRole("checkbox", { name: "Failed first" })).not.toBeInTheDocument();
    expect(artifactApi).not.toHaveBeenCalled();
    expect(genericApi).toHaveBeenCalledWith({
      ids: [validator.id],
      checksOffset: 20,
      checksLimit: 20,
    });
  });
});
