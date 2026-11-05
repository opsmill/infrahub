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

  test("saves only the instance label and color, leaving the date fields untouched", async () => {
    // GIVEN
    const component = await render(<InstanceIdentityForm />);
    await component.getByLabelText("Instance label").fill("us-east-1 PROD");

    // WHEN
    await component.getByRole("button", { name: "Save instance identity" }).click();

    // THEN
    await vi.waitFor(() => {
      expect(updateGlobalPreference).toHaveBeenCalledWith({
        instanceLabel: "us-east-1 PROD",
        instanceColor: "RED",
      });
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
      expect(updateGlobalPreference).toHaveBeenCalledWith({
        instanceLabel: null,
        instanceColor: "RED",
      });
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
    await expect
      .element(component.getByText("The instance label cannot be longer than 32 characters."))
      .toBeVisible();
  });

  test("does not save a label that exceeds the limit", async () => {
    // GIVEN
    const component = await render(<InstanceIdentityForm />);
    const input = component.getByLabelText("Instance label");
    await input.fill(TOO_LONG_LABEL);

    // WHEN
    await userEvent.keyboard("{Enter}");

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Save instance identity" }))
      .toBeDisabled();
    expect(updateGlobalPreference).not.toHaveBeenCalled();
  });

  test("toasts the error when the save fails", async () => {
    // GIVEN
    vi.mocked(updateGlobalPreference).mockRejectedValue(new Error("Not allowed"));
    const component = await render(<InstanceIdentityForm />);
    await component.getByLabelText("Instance label").fill("QA");

    // WHEN
    await component.getByRole("button", { name: "Save instance identity" }).click();

    // THEN
    await expect.element(component.getByText("Not allowed")).toBeVisible();
  });
});
