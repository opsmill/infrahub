import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { userEvent } from "vitest/browser";

import type { GlobalPreferences } from "@/entities/preferences/domain/model/preference";
import { getGlobalPreferences } from "@/entities/preferences/domain/use-cases/get-global-preferences";
import { updateGlobalPreference } from "@/entities/preferences/domain/use-cases/update-global-preference";

import { render } from "../../../../tests/components/render";
import { InstanceIdentityForm } from "./instance-identity-form";

vi.mock("@/entities/preferences/domain/use-cases/get-global-preferences");
vi.mock("@/entities/preferences/domain/use-cases/update-global-preference");

const baseGlobal: GlobalPreferences = {
  dateFormat: "ISO_DATETIME",
  timezone: "Asia/Tokyo",
  instanceLabel: "us-east-1",
  instanceColor: "RED",
};

const TOO_LONG_LABEL = "a".repeat(33);
const LENGTH_RULE = "The instance label cannot be longer than 32 characters.";

describe("InstanceIdentityForm", () => {
  beforeEach(() => {
    vi.mocked(getGlobalPreferences).mockResolvedValue(baseGlobal);
    vi.mocked(updateGlobalPreference).mockResolvedValue();
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  test("prefills the label and the color from the global preferences", async () => {
    // GIVEN
    vi.mocked(getGlobalPreferences).mockResolvedValue({
      ...baseGlobal,
      instanceLabel: "us-east-1 PROD",
    });

    // WHEN
    const component = await render(<InstanceIdentityForm />);

    // THEN
    await expect.element(component.getByLabelText("Instance label")).toHaveValue("us-east-1 PROD");
    await expect
      .element(component.getByRole("button", { name: "Instance color" }))
      .toHaveTextContent("Red");
  });

  test("sends only the label when only the label changed", async () => {
    // GIVEN
    const component = await render(<InstanceIdentityForm />);
    await component.getByLabelText("Instance label").fill("us-east-1 PROD");

    // WHEN
    await component.getByRole("button", { name: "Save instance identity" }).click();

    // THEN
    // toStrictEqual fails on an `instanceColor: undefined` key, which the API would still send.
    await vi.waitFor(() => {
      expect(vi.mocked(updateGlobalPreference).mock.calls).toStrictEqual([
        [{ instanceLabel: "us-east-1 PROD" }],
      ]);
    });
    await expect.element(component.getByText("Instance identity updated")).toBeVisible();
  });

  test("clears the label by sending null", async () => {
    // GIVEN
    const component = await render(<InstanceIdentityForm />);
    await component.getByLabelText("Instance label").fill("   ");

    // WHEN
    await component.getByRole("button", { name: "Save instance identity" }).click();

    // THEN
    await vi.waitFor(() => {
      expect(updateGlobalPreference).toHaveBeenCalledWith({ instanceLabel: null });
    });
  });

  test("sends only the color when only the color changed", async () => {
    // GIVEN
    const component = await render(<InstanceIdentityForm />);
    await component.getByRole("button", { name: "Instance color" }).click();
    await component.getByRole("option", { name: "Green", exact: true }).click();

    // WHEN
    await component.getByRole("button", { name: "Save instance identity" }).click();

    // THEN
    await vi.waitFor(() => {
      expect(vi.mocked(updateGlobalPreference).mock.calls).toStrictEqual([
        [{ instanceColor: "GREEN" }],
      ]);
    });
  });

  test("clears the color by sending null when the current color is picked again", async () => {
    // GIVEN
    const component = await render(<InstanceIdentityForm />);
    await component.getByRole("button", { name: "Instance color" }).click();
    await component.getByRole("option", { name: "Red", exact: true }).click();

    // WHEN
    await component.getByRole("button", { name: "Save instance identity" }).click();

    // THEN
    await vi.waitFor(() => {
      expect(updateGlobalPreference).toHaveBeenCalledWith({ instanceColor: null });
    });
  });

  test("shows the character count of the label being typed", async () => {
    // GIVEN
    const component = await render(<InstanceIdentityForm />);

    // WHEN
    await component.getByLabelText("Instance label").fill("QA");

    // THEN
    await expect.element(component.getByText("2/32")).toBeVisible();
  });

  test("names the 32-character limit as soon as the label exceeds it", async () => {
    // GIVEN
    const component = await render(<InstanceIdentityForm />);

    // WHEN
    await component.getByLabelText("Instance label").fill(TOO_LONG_LABEL);

    // THEN
    await expect.element(component.getByText(LENGTH_RULE)).toBeVisible();
  });

  test("does not save a label that exceeds the limit", async () => {
    // GIVEN
    const component = await render(<InstanceIdentityForm />);
    const input = component.getByLabelText("Instance label");
    await input.fill(TOO_LONG_LABEL);

    // WHEN
    await userEvent.keyboard("{Enter}");

    // THEN
    await expect.element(component.getByText(LENGTH_RULE)).toBeVisible();
    expect(updateGlobalPreference).not.toHaveBeenCalled();
  });

  test("names the rule on save when the stored label already exceeds the limit", async () => {
    // GIVEN
    vi.mocked(getGlobalPreferences).mockResolvedValue({
      ...baseGlobal,
      instanceLabel: TOO_LONG_LABEL,
    });
    const component = await render(<InstanceIdentityForm />);
    await component.getByRole("button", { name: "Instance color" }).click();
    await component.getByRole("option", { name: "Green", exact: true }).click();

    // WHEN
    await component.getByRole("button", { name: "Save instance identity" }).click();

    // THEN
    await expect.element(component.getByText(LENGTH_RULE)).toBeVisible();
    expect(updateGlobalPreference).not.toHaveBeenCalled();
  });

  test("keeps the typed label and the save button enabled when the save fails", async () => {
    // GIVEN
    vi.mocked(updateGlobalPreference).mockRejectedValue(new Error("Not allowed"));
    const component = await render(<InstanceIdentityForm />);
    await component.getByLabelText("Instance label").fill("QA");

    // WHEN
    await component.getByRole("button", { name: "Save instance identity" }).click();

    // THEN
    await expect.element(component.getByText("Not allowed")).toBeVisible();
    await expect.element(component.getByLabelText("Instance label")).toHaveValue("QA");
    await expect
      .element(component.getByRole("button", { name: "Save instance identity" }))
      .toBeEnabled();
  });

  test("disables the save button again once the save succeeds", async () => {
    // GIVEN
    const component = await render(<InstanceIdentityForm />);
    await component.getByLabelText("Instance label").fill("QA");

    // WHEN
    await component.getByRole("button", { name: "Save instance identity" }).click();

    // THEN
    await expect.element(component.getByText("Instance identity updated")).toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "Save instance identity" }))
      .toBeDisabled();
  });

  test("sends nothing for a label retyped with the saved text", async () => {
    // GIVEN
    const component = await render(<InstanceIdentityForm />);
    await component.getByLabelText("Instance label").fill("  us-east-1  ");

    // WHEN
    await component.getByRole("button", { name: "Save instance identity" }).click();

    // THEN
    await vi.waitFor(() => {
      expect(vi.mocked(updateGlobalPreference).mock.calls).toStrictEqual([[{}]]);
    });
  });
});
