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
  artifactApi.mockImplementation(async ({ ids, checksOffset }) => {
    const validatorId = ids?.[0] ?? "artifact-validator";
    const checkIds = checksOffset
      ? [`${validatorId}-next-page`]
      : [`${validatorId}-failed-z`, `${validatorId}-success-a`];
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
  test("automatically requests failed first and displays the server's card order", async () => {
    // GIVEN
    const validator = generateArtifactValidator();
    const component = await render(<Validator validator={validator} />);

    // WHEN
    await component.getByText(validator.display_label!).click();

    // THEN
    await expect.element(component.getByText("artifact-validator-failed-z")).toBeVisible();
    await expect.element(component.getByText("artifact-validator-success-a")).toBeVisible();
    expect(component.getByRole("checkbox", { name: "Failed first" })).not.toBeInTheDocument();
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

  test("changing one artifact's page leaves another artifact and global pagination unchanged", async () => {
    // GIVEN
    const first = generateArtifactValidator();
    const second = generateArtifactValidator({
      id: "second",
      display_label: "Artifact Validator: Other",
    });
    const params = new URLSearchParams({
      "artifact-checks-second": JSON.stringify({ limit: 20, offset: 20 }),
      pagination: JSON.stringify({ limit: 50, offset: 50 }),
    });
    window.history.replaceState(null, "", `?${params}`);
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
      ([request]) => request.ids?.[0] === "second"
    ).length;

    // WHEN
    await component
      .getByRole("region", { name: "First artifact" })
      .getByRole("button", { name: "Next page" })
      .click();

    // THEN
    await expect.element(component.getByText("artifact-validator-next-page")).toBeVisible();
    await expect.element(component.getByText("second-next-page")).toBeVisible();
    expect(artifactApi).toHaveBeenLastCalledWith({
      ids: [first.id],
      checksOffset: 10,
      checksLimit: 10,
      checksFailedFirst: true,
    });
    await expect
      .element(
        component
          .getByRole("region", { name: "First artifact" })
          .getByRole("button", { name: /Page 2/ })
      )
      .toHaveAttribute("aria-current", "page");
    expect(
      artifactApi.mock.calls.filter(([request]) => request.ids?.[0] === "second")
    ).toHaveLength(secondCallsBefore);
    const updatedParams = new URLSearchParams(window.location.search);
    expect(updatedParams.get("artifact-checks-second")).toBe(params.get("artifact-checks-second"));
    expect(updatedParams.get("pagination")).toBe(params.get("pagination"));
  });

  test.each([20, 50])("keeps failed-first ordering with page size %s", async (pageSize) => {
    // GIVEN
    const validator = generateArtifactValidator();
    const component = await render(<Validator validator={validator} />);
    await component.getByText(validator.display_label!).click();
    await component.getByRole("combobox").click();

    // WHEN
    await component.getByRole("option", { name: String(pageSize), exact: true }).click();

    // THEN
    await expect.element(component.getByRole("combobox")).toHaveTextContent(String(pageSize));
    expect(artifactApi).toHaveBeenLastCalledWith({
      ids: [validator.id],
      checksOffset: 0,
      checksLimit: pageSize,
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
    expect(artifactApi).not.toHaveBeenCalled();
    expect(genericApi).toHaveBeenCalledWith({
      ids: [validator.id],
      checksOffset: 20,
      checksLimit: 20,
    });
  });
});
