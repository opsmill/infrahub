import { useState } from "react";
import { describe, expect, test } from "vitest";

import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@/shared/components/ui/combobox";

import { render } from "../../../../tests/components/render";

/**
 * Minimal harness over the SHARED combobox primitives (no preferences code): a
 * controlled popover whose list carries `activeValue={selected}`, mirroring how
 * `ComboboxField` wires the currently-selected option. A long list with a mixed-case,
 * non-alphanumeric selected value ("Europe/Paris" style) exercises the regression:
 * cmdk otherwise activates the FIRST item on open instead of the selected one.
 */
function TestCombobox({
  options,
  selected,
}: {
  options: ReadonlyArray<{ value: string; label: string }>;
  selected: string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <Combobox open={open} onOpenChange={setOpen}>
      <ComboboxTrigger aria-label="test-combobox">
        {options.find((o) => o.value === selected)?.label ?? selected}
      </ComboboxTrigger>
      <ComboboxContent>
        <ComboboxList placeholder="Filter..." activeValue={selected}>
          <ComboboxEmpty>No match found.</ComboboxEmpty>
          {options.map((o) => (
            <ComboboxItem key={o.value} value={o.value} selectedValue={selected}>
              {o.label}
            </ComboboxItem>
          ))}
        </ComboboxList>
      </ComboboxContent>
    </Combobox>
  );
}

// A long list so the selected option lives far from the top (as with the timezone list).
const longOptions = Array.from({ length: 60 }, (_, i) => ({
  value: `Zone/City-${i}`,
  label: `Zone/City-${i}`,
}));

describe("Combobox active/selected option on open", () => {
  test("activates the currently-selected option (not the first) when opened", async () => {
    const selected = "Zone/City-42"; // mixed-case, contains '/' and '-'
    const component = await render(<TestCombobox options={longOptions} selected={selected} />);

    await component.getByRole("combobox", { name: "test-combobox" }).click();

    // cmdk marks its active/highlighted item with aria-selected="true". It must be the
    // selected option, not the first item — verifies both the highlight and, via
    // scrollIntoView, that the right row is targeted.
    const activeOption = component.getByRole("option", { name: selected, exact: true });
    await expect.element(activeOption).toHaveAttribute("aria-selected", "true");

    const firstOption = component.getByRole("option", { name: "Zone/City-0", exact: true });
    await expect.element(firstOption).toHaveAttribute("aria-selected", "false");
  });

  test("renders the check indicator on the selected option and keeps mixed-case exact match", async () => {
    const selected = "ISO_DATETIME"; // upper-case + underscore, like a real preset value
    const options = [
      { value: "EU_DATETIME", label: "EU_DATETIME" },
      { value: "ISO_DATETIME", label: "ISO_DATETIME" },
      { value: "US_DATETIME", label: "US_DATETIME" },
    ];
    const component = await render(<TestCombobox options={options} selected={selected} />);

    await component.getByRole("combobox", { name: "test-combobox" }).click();

    // The selected option is the active one despite its casing (cmdk matches the active
    // item case-sensitively on the trimmed value; only its search filter lowercases).
    const selectedOption = component.getByRole("option", { name: selected, exact: true });
    await expect.element(selectedOption).toHaveAttribute("aria-selected", "true");

    // The green check is not opacity-0'd on the selected row (indicator is correct).
    const check = selectedOption.element().querySelector(".text-green-900");
    expect(check).not.toBeNull();
    expect(check?.className).not.toContain("opacity-0");
  });

  test("keyboard navigation still moves the highlight (no frozen active item)", async () => {
    const { userEvent } = await import("vitest/browser");
    const selected = "Zone/City-10";
    const component = await render(<TestCombobox options={longOptions} selected={selected} />);

    await component.getByRole("combobox", { name: "test-combobox" }).click();

    const start = component.getByRole("option", { name: selected, exact: true });
    await expect.element(start).toHaveAttribute("aria-selected", "true");

    // ArrowDown should move the highlight off the seeded value onto the next item.
    await userEvent.keyboard("{ArrowDown}");
    const next = component.getByRole("option", { name: "Zone/City-11", exact: true });
    await expect.element(next).toHaveAttribute("aria-selected", "true");
    await expect.element(start).toHaveAttribute("aria-selected", "false");
  });
});
