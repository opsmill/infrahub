import { afterEach, describe, expect, it, vi } from "vitest";
import { userEvent } from "vitest/browser";

import type { NumberPoolDivision } from "@/entities/resource-manager/domain/model/number-pool";
import type { NumberPoolDivisionSort } from "@/entities/resource-manager/ui/hooks/use-number-pool-division-table-state";

import { render } from "../../../../../../tests/components/render";
import {
  generateNumberPoolDivision,
  generateNumberPoolDivisionEntry,
  generateNumberPoolUsage,
} from "../../../../../../tests/fake/number-pool";
import { NumberPoolDivisionsTable } from "./number-pool-divisions-table";

const initialUrl = window.location.href;

const fields = [
  { name: "device", label: "Device" },
  { name: "role", label: "Role" },
];

const division = generateNumberPoolDivision({
  entries: [
    generateNumberPoolDivisionEntry({ path: "device", value: "device-id", label: "atl1-core1" }),
    generateNumberPoolDivisionEntry({ path: "role", value: "", label: "", peerKind: null }),
  ],
  usage: generateNumberPoolUsage(),
});

const divisionUrlPath = `/resource-manager/pool-id?allocation_scope=${encodeURIComponent(
  JSON.stringify(["device-id", ""])
)}`;

const usageSort: NumberPoolDivisionSort = { by: "usage", direction: "descending" };

const renderTable = ({
  divisions = [division],
  sort = usageSort,
  onSortChange = vi.fn(),
}: {
  divisions?: NumberPoolDivision[];
  sort?: NumberPoolDivisionSort;
  onSortChange?: (sort: NumberPoolDivisionSort) => void;
} = {}) =>
  render(
    <div className="h-80 w-96 overflow-auto">
      <NumberPoolDivisionsTable
        poolId="pool-id"
        fields={fields}
        divisions={divisions}
        sort={sort}
        onSortChange={onSortChange}
      />
    </div>
  );

const usageHeaderOf = (component: Awaited<ReturnType<typeof renderTable>>) => {
  const header = component.getByRole("button", { name: "Usage" }).element().closest("th");
  if (!header) throw new Error("The usage column has no header cell");
  return header;
};

describe("NumberPoolDivisionsTable", () => {
  afterEach(() => {
    window.history.replaceState(null, "", initialUrl);
  });

  it("shows one column per field in the pool's order, then usage", async () => {
    // WHEN
    const component = await renderTable();

    // THEN
    await expect
      .element(component.getByRole("row").first())
      .toHaveTextContent(/^Device\s*Role\s*Usage/);
  });

  it("keeps the usage column pinned on the right edge", async () => {
    // WHEN
    const component = await renderTable();

    // THEN
    const usageHeader = usageHeaderOf(component);
    expect(getComputedStyle(usageHeader).position).toBe("sticky");
    expect(getComputedStyle(usageHeader).right).toBe("0px");
  });

  it("links the first cell to the allocation scope", async () => {
    // WHEN
    const component = await renderTable();

    // THEN
    await expect
      .element(component.getByRole("link", { name: /atl1-core1/ }))
      .toHaveAttribute("href", divisionUrlPath);
  });

  it("opens the allocation scope when the operator clicks elsewhere on the row", async () => {
    // GIVEN
    const component = await renderTable();

    // WHEN
    await userEvent.click(component.getByText("No value"));

    // THEN
    expect(`${window.location.pathname}${window.location.search}`).toBe(divisionUrlPath);
  });

  it("shows an empty value as no value", async () => {
    // WHEN
    const component = await renderTable();

    // THEN
    await expect.element(component.getByText("No value")).toBeVisible();
  });

  it("marks the sorted column and sorts a field in ascending order first", async () => {
    // GIVEN
    const onSortChange = vi.fn();
    const component = await renderTable({ onSortChange });

    // WHEN
    await userEvent.click(component.getByRole("button", { name: "Device" }));

    // THEN
    expect(usageHeaderOf(component).getAttribute("aria-sort")).toBe("descending");
    expect(onSortChange).toHaveBeenCalledWith({ by: "device", direction: "ascending" });
  });
});
