/** React Aria tooltips need a prior pointer interaction; call once before a `.hover()` that opens one. */
export async function initPointerTracking(locator: {
  click(options?: { position?: { x: number; y: number } }): Promise<void>;
}) {
  await locator.click({ position: { x: 0, y: 0 } });
}

/**
 * Open the shared Combobox (`triggerName` = field label) and click the option whose exact visible
 * text is `optionName` (exact so "yyyy-MM-dd" can't match "yyyy-MM-dd HH:mm"). For long lists (e.g.
 * timezones), pass `filter` — typed into cmdk's auto-focused search box — to narrow first.
 */
export async function selectComboboxOption(
  component: {
    getByRole: (
      role: string,
      options?: { name?: string | RegExp; exact?: boolean }
    ) => { click(): Promise<void> };
  },
  triggerName: string | RegExp,
  optionName: string,
  filter?: string
) {
  await component.getByRole("combobox", { name: triggerName }).click();
  if (filter !== undefined) {
    // The cmdk search box auto-focuses on open; type into the focused element.
    const { userEvent } = await import("vitest/browser");
    await userEvent.keyboard(filter);
  }
  await component.getByRole("option", { name: optionName, exact: true }).click();
}
