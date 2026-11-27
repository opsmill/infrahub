import type React from "react";
import { describe, expect, it } from "vitest";

import { Form, FormActions, FormSubmit, findErrorMessage } from "@/shared/components/ui/form";
import { classNames } from "@/shared/utils/common";

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

const OVERFLOWING_FIELDS_CLASS = "h-150";
const FITTING_FIELDS_CLASS = "h-12";

interface ScrollableFormProps {
  fieldsClassName: string;
  scrollAreaClassName?: string;
  aboveFormClassName?: string;
  children?: React.ReactNode;
}

const ScrollableForm = ({
  fieldsClassName,
  scrollAreaClassName = "p-3",
  aboveFormClassName = "h-0",
  children,
}: ScrollableFormProps) => (
  <div data-testid="scroll-area" className={classNames("h-50 overflow-auto", scrollAreaClassName)}>
    <div data-testid="above-form" className={aboveFormClassName} />
    <Form>
      <div className={fieldsClassName} />
      {children}
      <FormActions data-testid="form-actions">
        <FormSubmit>Save</FormSubmit>
      </FormActions>
    </Form>
  </div>
);

type RenderedForm = Awaited<ReturnType<typeof render>>;

// Intersection observers report once after the first frame, so waiting past it keeps that report from standing in for a later update.
const waitForFirstFrames = () =>
  new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));

const getVisibleBottom = (component: RenderedForm) => {
  const scrollArea = component.getByTestId("scroll-area").element();
  return scrollArea.getBoundingClientRect().top + scrollArea.clientTop + scrollArea.clientHeight;
};

describe("FormActions", () => {
  it("keeps the buttons at the edge of the scroll area, above a separator, while fields are hidden beneath them", async () => {
    // GIVEN
    const fieldsClassName = OVERFLOWING_FIELDS_CLASS;

    // WHEN
    const component = await render(<ScrollableForm fieldsClassName={fieldsClassName} />);

    // THEN
    const actionsElement = component.getByTestId("form-actions").element();
    expect(actionsElement).toHaveAttribute("data-pinned");
    expect(actionsElement.getBoundingClientRect().bottom).toBeCloseTo(
      getVisibleBottom(component),
      0
    );
    expect(getComputedStyle(actionsElement).borderTopColor).not.toBe("rgba(0, 0, 0, 0)");
  });

  it("keeps the buttons fully in view in a scroll area without padding", async () => {
    // GIVEN
    const scrollAreaClassName = "p-0";

    // WHEN
    const component = await render(
      <ScrollableForm
        fieldsClassName={OVERFLOWING_FIELDS_CLASS}
        scrollAreaClassName={scrollAreaClassName}
      />
    );

    // THEN
    await expect.element(component.getByTestId("form-actions")).toHaveAttribute("data-pinned");
    const saveBottom = component
      .getByRole("button", { name: "Save" })
      .element()
      .getBoundingClientRect().bottom;
    expect(saveBottom).toBeLessThan(getVisibleBottom(component));
  });

  it("drops the separator once the end of the form is scrolled into view", async () => {
    // GIVEN
    const component = await render(<ScrollableForm fieldsClassName={OVERFLOWING_FIELDS_CLASS} />);
    await expect.element(component.getByTestId("form-actions")).toHaveAttribute("data-pinned");
    await waitForFirstFrames();

    // WHEN
    const scrollArea = component.getByTestId("scroll-area").element();
    scrollArea.scrollTop = scrollArea.scrollHeight;

    // THEN
    await expect.element(component.getByTestId("form-actions")).not.toHaveAttribute("data-pinned");
  });

  it("draws the separator when content above the form grows and pushes fields out of view", async () => {
    // GIVEN
    const component = await render(<ScrollableForm fieldsClassName={FITTING_FIELDS_CLASS} />);
    await waitForFirstFrames();

    // WHEN
    component
      .getByTestId("above-form")
      .element()
      .classList.replace("h-0", OVERFLOWING_FIELDS_CLASS);

    // THEN
    await expect.element(component.getByTestId("form-actions")).toHaveAttribute("data-pinned");
  });

  it("keeps a field scrolled into view at the bottom edge above the buttons", async () => {
    // GIVEN
    const component = await render(
      <ScrollableForm fieldsClassName={OVERFLOWING_FIELDS_CLASS}>
        <input aria-label="Last field" />
      </ScrollableForm>
    );
    const lastField = component.getByRole("textbox", { name: "Last field" }).element();

    // WHEN
    lastField.scrollIntoView({ block: "nearest" });

    // THEN
    await expect
      .poll(() => lastField.getBoundingClientRect().bottom)
      .toBeLessThanOrEqual(
        component.getByTestId("form-actions").element().getBoundingClientRect().top
      );
  });

  it("lets an option of a list inside the form scroll flush to the bottom of that list", async () => {
    // GIVEN
    const component = await render(
      <ScrollableForm fieldsClassName={FITTING_FIELDS_CLASS}>
        <div role="listbox" aria-label="Options" className="h-20 overflow-auto">
          <div className="h-50" />
          <div role="option" aria-selected={false} tabIndex={-1}>
            Highlighted option
          </div>
          <div className="h-50" />
        </div>
      </ScrollableForm>
    );
    const option = component.getByRole("option", { name: "Highlighted option" }).element();

    // WHEN
    option.scrollIntoView({ block: "nearest" });

    // THEN
    const list = component.getByRole("listbox", { name: "Options" }).element();
    await expect
      .poll(() => option.getBoundingClientRect().bottom)
      .toBeCloseTo(list.getBoundingClientRect().top + list.clientTop + list.clientHeight, 0);
  });

  it("draws no separator when every field fits in the scroll area", async () => {
    // GIVEN
    const fieldsClassName = FITTING_FIELDS_CLASS;

    // WHEN
    const component = await render(<ScrollableForm fieldsClassName={fieldsClassName} />);

    // THEN
    expect(component.getByTestId("form-actions").element()).not.toHaveAttribute("data-pinned");
  });
});
