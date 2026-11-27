import { describe, expect, it, test } from "vitest";

import { Form, FormActions, FormSubmit, findErrorMessage } from "@/shared/components/ui/form";

import { render } from "../../../../tests/components/render";

describe("findErrorMessage", () => {
  it("returns undefined when there is no error", () => {
    expect(findErrorMessage(undefined)).toBeUndefined();
    expect(findErrorMessage(null)).toBeUndefined();
  });

  it("returns a field's own error message", () => {
    expect(findErrorMessage({ type: "required", message: "Required", ref: {} })).toBe("Required");
  });

  it("descends into a nested child-field error", () => {
    // RHF nests child-field errors under the parent path, e.g. a from-pool
    // allocation's prefix-length field.
    const error = {
      value: {
        from_pool: { prefixLength: { type: "validate", message: "Value must be at most 128" } },
      },
    };
    expect(findErrorMessage(error)).toBe("Value must be at most 128");
  });

  it("ignores the type/ref keys and an empty message", () => {
    expect(findErrorMessage({ type: "validate", ref: {}, message: "" })).toBeUndefined();
  });

  it("returns undefined when no message exists anywhere in the tree", () => {
    expect(findErrorMessage({ value: { from_pool: { id: { ref: {} } } } })).toBeUndefined();
  });
});

const VISIBLE_HEIGHT = 200;

interface ScrollableFormProps {
  fieldsHeight: number;
}

const ScrollableForm = ({ fieldsHeight }: ScrollableFormProps) => (
  <div
    data-testid="scroll-container"
    className="overflow-auto p-3"
    style={{ height: VISIBLE_HEIGHT }}
  >
    <Form>
      <div style={{ height: fieldsHeight }} />
      <FormActions data-testid="form-actions">
        <FormSubmit>Save</FormSubmit>
      </FormActions>
    </Form>
  </div>
);

const getScrollContainer = (component: Awaited<ReturnType<typeof render>>) =>
  component.getByTestId("scroll-container").element() as HTMLElement;

const getFormActions = (component: Awaited<ReturnType<typeof render>>) =>
  component.getByTestId("form-actions").element() as HTMLElement;

// Observers are notified in creation order, so once this one reports, the bar's own observer has already reported.
const waitForIntersectionCheck = (component: Awaited<ReturnType<typeof render>>) =>
  new Promise<void>((resolve) => {
    const observer = new IntersectionObserver(
      () => {
        observer.disconnect();
        resolve();
      },
      { threshold: 1 }
    );
    observer.observe(getFormActions(component));
  });

describe("FormActions", () => {
  test("stays in view with a separator while fields are hidden beneath it", async () => {
    // GIVEN
    const fieldsHeight = VISIBLE_HEIGHT * 3;

    // WHEN
    const component = await render(<ScrollableForm fieldsHeight={fieldsHeight} />);

    // THEN
    await expect.element(component.getByTestId("form-actions")).toHaveAttribute("data-stuck");
    const containerBottom = getScrollContainer(component).getBoundingClientRect().bottom;
    const buttonBottom = component
      .getByRole("button", { name: "Save" })
      .element()
      .getBoundingClientRect().bottom;
    expect(buttonBottom).toBeLessThanOrEqual(containerBottom);
  });

  test("drops the separator once the last field is scrolled into view", async () => {
    // GIVEN
    const component = await render(<ScrollableForm fieldsHeight={VISIBLE_HEIGHT * 3} />);
    await expect.element(component.getByTestId("form-actions")).toHaveAttribute("data-stuck");

    // WHEN
    const scrollContainer = getScrollContainer(component);
    scrollContainer.scrollTop = scrollContainer.scrollHeight;

    // THEN
    await expect.element(component.getByTestId("form-actions")).not.toHaveAttribute("data-stuck");
  });

  test("draws no separator when every field fits in view", async () => {
    // GIVEN
    const fieldsHeight = VISIBLE_HEIGHT / 4;

    // WHEN
    const component = await render(<ScrollableForm fieldsHeight={fieldsHeight} />);
    await waitForIntersectionCheck(component);

    // THEN
    expect(getFormActions(component)).not.toHaveAttribute("data-stuck");
  });
});
