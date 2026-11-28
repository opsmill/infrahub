import { useState } from "react";
import { FormProvider, useForm } from "react-hook-form";
import { describe, expect, test, vi } from "vitest";

import { AuthContext, type AuthContextType } from "@/entities/authentication/ui/auth-provider";

import { render } from "../../../../../tests/components/render";
import { PcStateButton } from "./pc-state-button";

const signedIn: AuthContextType = {
  accessToken: "token",
  isAuthenticated: true,
  setToken: () => {},
  user: { id: "user-1" },
};

function CreateFormState({ onSubmit }: { onSubmit: () => void }) {
  const form = useForm();
  const [state, setState] = useState("open");

  return (
    <AuthContext value={signedIn}>
      <FormProvider {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)}>
          <PcStateButton state={state} setState={setState} />
        </form>
      </FormProvider>
    </AuthContext>
  );
}

describe("PcStateButton", () => {
  test("submits the create form from the Open button", async () => {
    // GIVEN
    const onSubmit = vi.fn();
    const component = await render(<CreateFormState onSubmit={onSubmit} />);

    // WHEN
    await component.getByRole("button", { name: "Open", exact: true }).click();

    // THEN
    await vi.waitFor(() => expect(onSubmit).toHaveBeenCalledOnce());
  });

  test("relabels the submit button after choosing Draft", async () => {
    // GIVEN
    const component = await render(<CreateFormState onSubmit={vi.fn()} />);
    await component.getByTestId("proposed-change-action-button-select").click();

    // WHEN
    await component.getByRole("option", { name: "Draft", exact: true }).click();

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Open a draft", exact: true }))
      .toBeVisible();
  });

  test("leaves the picker chevron without an accessible name", async () => {
    // GIVEN
    const onSubmit = vi.fn();

    // WHEN
    const component = await render(<CreateFormState onSubmit={onSubmit} />);

    // THEN
    const chevron = component.getByTestId("proposed-change-action-button-select");
    await expect.element(chevron).toBeEnabled();
    await expect.element(chevron).not.toHaveAttribute("aria-label");
  });
});
