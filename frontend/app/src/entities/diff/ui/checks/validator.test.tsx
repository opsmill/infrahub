import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { getCheckDetailsFromApi } from "@/entities/diff/api/get-check-details-from-api";
import { getValidatorDetailsFromApi } from "@/entities/diff/api/get-validator-details-from-api";

import { render } from "../../../../../tests/components/render";
import {
  generateArtifactCheck,
  generateArtifactValidator,
  generateDataCheck,
  generateDataValidator,
  generateValidatorDetails,
} from "../../../../../tests/fake/check";
import { Validator } from "./validator";

vi.mock("@/entities/diff/api/get-check-details-from-api");
vi.mock("@/entities/diff/api/get-validator-details-from-api");

const validatorApi = vi.mocked(getValidatorDetailsFromApi);
const checkApi = vi.mocked(getCheckDetailsFromApi);

beforeEach(() => {
  validatorApi.mockImplementation(async ({ ids, checksOffset }) => {
    const validatorId = ids?.[0] ?? "artifact-validator";
    const checkIds = checksOffset
      ? [`${validatorId}-next-page`]
      : [`${validatorId}-failed-z`, `${validatorId}-success-a`];
    return generateValidatorDetails({ validatorId, checkIds, count: 30 });
  });
  checkApi.mockImplementation(async ({ id }) => {
    const generateCheck = id.startsWith("data-") ? generateDataCheck : generateArtifactCheck;
    return {
      data: {
        CoreCheck: {
          edges: [
            {
              node: generateCheck({
                id,
                name: { value: id },
                conclusion: { value: id.endsWith("failed-z") ? "failure" : "success" },
              }),
            },
          ],
        },
      },
    };
  });
});

afterEach(() => {
  vi.resetAllMocks();
  window.history.replaceState(null, "", window.location.pathname);
});

describe("validator check ordering", () => {
  test.each(["artifact", "data"])(
    "displays the server's failed-first card order for %s validators without a checkbox",
    async (kind) => {
      // GIVEN
      const label = `${kind} validator`;
      const validator =
        kind === "artifact"
          ? generateArtifactValidator({ display_label: label })
          : generateDataValidator({ display_label: label });
      const component = await render(<Validator validator={validator} />);

      // WHEN
      await component.getByText(label).click();

      // THEN
      const failed = component.getByText(`${validator.id}-failed-z`);
      const succeeded = component.getByText(`${validator.id}-success-a`);
      await expect.element(failed).toBeVisible();
      await expect.element(succeeded).toBeVisible();
      expect(component.getByRole("checkbox", { name: "Failed first" })).not.toBeInTheDocument();
      expect(failed.element().compareDocumentPosition(succeeded.element())).toBe(
        Node.DOCUMENT_POSITION_FOLLOWING
      );
      expect(validatorApi).toHaveBeenCalledWith({
        ids: [validator.id],
        checksOffset: 0,
        checksLimit: 10,
      });
    }
  );

  test("changing a data validator's page leaves the artifact and global pagination unchanged", async () => {
    // GIVEN
    const first = generateDataValidator();
    const second = generateArtifactValidator({
      id: "second",
      display_label: "Artifact Validator: Other",
    });
    const params = new URLSearchParams({
      "validator-checks-second": JSON.stringify({ limit: 20, offset: 20 }),
      pagination: JSON.stringify({ limit: 50, offset: 50 }),
    });
    window.history.replaceState(null, "", `?${params}`);
    const component = await render(
      <>
        <section aria-label="Data checks">
          <Validator validator={first} />
        </section>
        <section aria-label="Artifact checks">
          <Validator validator={second} />
        </section>
      </>
    );
    await component.getByText("Data Integrity").click();
    await component.getByText("Artifact Validator: Other").click();
    await expect.element(component.getByText("second-next-page")).toBeVisible();
    const secondCallsBefore = validatorApi.mock.calls.filter(
      ([request]) => request.ids?.[0] === "second"
    ).length;

    // WHEN
    await component
      .getByRole("region", { name: "Data checks" })
      .getByRole("button", { name: "Next page" })
      .click();

    // THEN
    await expect.element(component.getByText("data-validator-next-page")).toBeVisible();
    await expect.element(component.getByText("second-next-page")).toBeVisible();
    expect(validatorApi).toHaveBeenLastCalledWith({
      ids: [first.id],
      checksOffset: 10,
      checksLimit: 10,
    });
    await expect
      .element(
        component
          .getByRole("region", { name: "Data checks" })
          .getByRole("button", { name: /Page 2/ })
      )
      .toHaveAttribute("aria-current", "page");
    expect(
      validatorApi.mock.calls.filter(([request]) => request.ids?.[0] === "second")
    ).toHaveLength(secondCallsBefore);
    const updatedParams = new URLSearchParams(window.location.search);
    expect(updatedParams.get("validator-checks-second")).toBe(
      params.get("validator-checks-second")
    );
    expect(updatedParams.get("pagination")).toBe(params.get("pagination"));
  });

  test.each([20, 50])("keeps the server's check order with page size %s", async (pageSize) => {
    // GIVEN
    const validator = generateArtifactValidator();
    const component = await render(<Validator validator={validator} />);
    await component.getByText("Artifact Validator: Startup Config").click();
    await component.getByRole("combobox").click();

    // WHEN
    await component.getByRole("option", { name: String(pageSize), exact: true }).click();

    // THEN
    await expect.element(component.getByRole("combobox")).toHaveTextContent(String(pageSize));
    expect(validatorApi).toHaveBeenLastCalledWith({
      ids: [validator.id],
      checksOffset: 0,
      checksLimit: pageSize,
    });
    expect(
      component
        .getByText("artifact-validator-failed-z")
        .element()
        .compareDocumentPosition(component.getByText("artifact-validator-success-a").element())
    ).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });

  test("restores a non-artifact validator's page from its own URL parameter", async () => {
    // GIVEN
    const validator = generateDataValidator();
    window.history.replaceState(
      null,
      "",
      `?${new URLSearchParams({
        "validator-checks-data-validator": JSON.stringify({ limit: 20, offset: 20 }),
        pagination: JSON.stringify({ limit: 50, offset: 50 }),
      })}`
    );
    const component = await render(<Validator validator={validator} />);

    // WHEN
    await component.getByText("Data Integrity").click();

    // THEN
    await expect.element(component.getByText("data-validator-next-page")).toBeVisible();
    expect(validatorApi).toHaveBeenCalledWith({
      ids: [validator.id],
      checksOffset: 20,
      checksLimit: 20,
    });
    await expect.element(component.getByRole("combobox")).toHaveTextContent("20");
  });
});
