import { createRef } from "react";
import { describe, expect, it, test } from "vitest";

import { type FormRef, findErrorMessage } from "@/shared/components/ui/form";

import { TestForm } from "../../../../tests/components/form.story";
import { render } from "../../../../tests/components/render";

describe("Form", () => {
  test("resets to the values the submit handler returns as resetTo", async () => {
    // GIVEN
    const formRef = createRef<FormRef>();
    const component = await render(
      <TestForm
        ref={formRef}
        defaultValues={{ name: "typed" }}
        onSubmit={() => ({ resetTo: { name: "saved" } })}
      />
    );

    // WHEN
    await component.getByRole("button", { name: "Submit" }).click();

    // THEN
    await expect.poll(() => formRef.current?.getValues("name")).toBe("saved");
  });

  test("resets to the submitted values when the submit handler returns any other value", async () => {
    // GIVEN
    const formRef = createRef<FormRef>();
    const component = await render(
      <TestForm
        ref={formRef}
        defaultValues={{ name: "initial" }}
        onSubmit={async () => new URLSearchParams({ name: "from-url" })}
      />
    );
    formRef.current?.setValue("name", "typed", { shouldDirty: true });

    // WHEN
    await component.getByRole("button", { name: "Submit" }).click();

    // THEN
    await expect.poll(() => formRef.current?.formState.defaultValues?.name).toBe("typed");
    expect(formRef.current?.getValues("name")).toBe("typed");
  });

  test("resets to the submitted values when the submit handler returns nothing", async () => {
    // GIVEN
    const formRef = createRef<FormRef>();
    const component = await render(<TestForm ref={formRef} defaultValues={{ name: "initial" }} />);
    formRef.current?.setValue("name", "typed", { shouldDirty: true });

    // WHEN
    await component.getByRole("button", { name: "Submit" }).click();

    // THEN
    await expect.poll(() => formRef.current?.formState.defaultValues?.name).toBe("typed");
    expect(formRef.current?.getValues("name")).toBe("typed");
  });
});

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
