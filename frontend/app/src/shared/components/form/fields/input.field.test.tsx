import { describe, expect, test } from "vitest";
import { userEvent } from "vitest/browser";

import { DynamicField } from "@/shared/components/form/dynamic-form";
import type { FormAttributeValue } from "@/shared/components/form/type";

import { ATTRIBUTE_KIND } from "@/entities/schema/domain/model/attribute-kind";

import { TestForm } from "../../../../../tests/components/form.story";
import { render } from "../../../../../tests/components/render";

// 111 characters: long enough that a single-line input clips it.
const LONG_DESCRIPTION =
  "Very long description that is still smaller than the current limit of 128 characters. Would be good to fix that";

// A field that can scroll is a field that clips: the full value is in the DOM
// and counts as "visible" even when the rendering cuts it off, so visibility
// assertions cannot catch this bug.
const hiddenPixels = (element: HTMLElement) => {
  element.scrollLeft = 1e6;
  element.scrollTop = 1e6;
  const hidden = { x: element.scrollLeft, y: element.scrollTop };
  element.scrollLeft = 0;
  element.scrollTop = 0;
  return hidden;
};

// Match the width of the drawer that hosts object create/edit forms; on a
// full-width form the long value fits and the clipping probes prove nothing.
const DRAWER_WIDTH = 400;

describe("Text attribute field", () => {
  test("shows a long typed value without clipping in the create form", async () => {
    // GIVEN
    const component = await render(
      <div style={{ width: DRAWER_WIDTH }}>
        <TestForm>
          <DynamicField type={ATTRIBUTE_KIND.TEXT} name="description" label="Description" />
        </TestForm>
      </div>
    );
    const input = component.getByLabelText("Description");

    // WHEN
    await input.fill(LONG_DESCRIPTION);

    // THEN
    await expect.element(input).toHaveValue(LONG_DESCRIPTION);
    expect(hiddenPixels(input.element() as HTMLElement)).toEqual({ x: 0, y: 0 });
  });

  test("shows a long stored value without clipping in the edit form", async () => {
    // GIVEN
    const defaultValue: FormAttributeValue = {
      source: { type: "user" },
      value: LONG_DESCRIPTION,
    };

    // WHEN
    const component = await render(
      <div style={{ width: DRAWER_WIDTH }}>
        <TestForm>
          <DynamicField
            type={ATTRIBUTE_KIND.TEXT}
            name="description"
            label="Description"
            defaultValue={defaultValue}
          />
        </TestForm>
      </div>
    );

    // THEN
    const input = component.getByLabelText("Description");
    await expect.element(input).toHaveValue(LONG_DESCRIPTION);
    expect(hiddenPixels(input.element() as HTMLElement)).toEqual({ x: 0, y: 0 });
  });

  test("strips newlines from pasted content", async () => {
    // GIVEN
    const component = await render(
      <TestForm>
        <DynamicField type={ATTRIBUTE_KIND.TEXT} name="description" label="Description" />
      </TestForm>
    );
    const input = component.getByLabelText("Description");

    // WHEN
    await input.fill("first line\nsecond line");

    // THEN
    await expect.element(input).toHaveValue("first line second line");
  });

  test("submits the form when pressing Enter", async () => {
    // GIVEN
    let submittedValue: unknown;
    const component = await render(
      <TestForm onSubmit={(data) => (submittedValue = data)}>
        <DynamicField type={ATTRIBUTE_KIND.TEXT} name="description" label="Description" />
      </TestForm>
    );
    const input = component.getByLabelText("Description");
    await input.fill("a value");

    // WHEN
    await userEvent.keyboard("{enter}");

    // THEN
    await expect
      .poll(() => submittedValue)
      .toEqual({ description: { source: { type: "user" }, value: "a value" } });
  });

  test("does not submit when Enter confirms an IME composition", async () => {
    // GIVEN
    let submitCount = 0;
    const component = await render(
      <TestForm onSubmit={() => (submitCount += 1)}>
        <DynamicField type={ATTRIBUTE_KIND.TEXT} name="description" label="Description" />
      </TestForm>
    );
    const input = component.getByLabelText("Description");
    await input.fill("a value");

    // WHEN
    input.element().dispatchEvent(
      new KeyboardEvent("keydown", {
        key: "Enter",
        isComposing: true,
        bubbles: true,
        cancelable: true,
      })
    );

    // THEN
    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(submitCount).toBe(0);
  });

  test("does not submit again when Enter is pressed while a save is pending", async () => {
    // GIVEN
    let submitCount = 0;
    const component = await render(
      <TestForm
        onSubmit={() => {
          submitCount += 1;
          // A promise that never settles keeps the form in its submitting state.
          return new Promise(() => {});
        }}
      >
        <DynamicField type={ATTRIBUTE_KIND.TEXT} name="description" label="Description" />
      </TestForm>
    );
    const input = component.getByLabelText("Description");
    await input.fill("a value");
    await userEvent.keyboard("{enter}");
    await expect
      .element(component.getByRole("button", { name: "Submit" }))
      .toHaveAttribute("data-pending");

    // WHEN
    await userEvent.keyboard("{enter}");

    // THEN
    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(submitCount).toBe(1);
  });
});
