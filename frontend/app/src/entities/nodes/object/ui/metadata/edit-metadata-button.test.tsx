import { describe, expect, it, vi } from "vitest";

import { render } from "../../../../../../tests/components/render";
import { EditMetadataButton } from "./edit-metadata-button";

describe("EditMetadataButton", () => {
  it("runs the edit action when the user is allowed to update", async () => {
    // GIVEN
    const onPress = vi.fn();
    const component = await render(
      <EditMetadataButton onPress={onPress} permission={{ isAllowed: true }} />
    );

    // WHEN
    await component.getByRole("button", { name: "Edit metadata" }).click();

    // THEN
    expect(onPress).toHaveBeenCalledOnce();
  });

  it("cannot be pressed when the user is not allowed to update", async () => {
    // WHEN
    const component = await render(
      <EditMetadataButton
        onPress={vi.fn()}
        permission={{ isAllowed: false, message: "You do not have permission to update" }}
      />
    );

    // THEN
    await expect.element(component.getByRole("button", { name: "Edit metadata" })).toBeDisabled();
  });
});
