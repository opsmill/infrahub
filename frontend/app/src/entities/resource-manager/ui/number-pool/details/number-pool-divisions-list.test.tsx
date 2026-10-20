import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { userEvent } from "vitest/browser";
import { cleanup } from "vitest-browser-react";

import { store } from "@/shared/stores";

import type { NumberPoolDivisions } from "@/entities/resource-manager/domain/model/number-pool";
import { useGetNumberPoolDivisions } from "@/entities/resource-manager/ui/queries/get-number-pool-divisions.query";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../../tests/components/render";
import {
  generateNumberPoolData,
  generateNumberPoolDivision,
  generateNumberPoolDivisionEntry,
  generateNumberPoolDivisions,
  generateNumberPoolUsage,
} from "../../../../../../tests/fake/number-pool";
import {
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../../../tests/fake/schema";
import { NumberPoolDivisionsList } from "./number-pool-divisions-list";

vi.mock("@/entities/resource-manager/ui/queries/get-number-pool-divisions.query", () => ({
  useGetNumberPoolDivisions: vi.fn(),
}));

const initialNodeSchemas = store.get(nodeSchemasAtom);
const initialUrl = window.location.href;

const pool = generateNumberPoolData({ allocation_scope: { value: ["device"] } });

const interfaceSchema = generateNodeSchema({
  kind: "InfraInterface",
  name: "Interface",
  namespace: "Infra",
  relationships: [generateRelationshipSchema({ name: "device", label: "Device" })],
});

const deviceDivision = (label: string, utilization: number) =>
  generateNumberPoolDivision({
    label,
    entries: [generateNumberPoolDivisionEntry({ value: `${label}-id`, label })],
    usage: generateNumberPoolUsage({ utilization }),
  });

const mockDivisions = (data: NumberPoolDivisions) =>
  vi.mocked(useGetNumberPoolDivisions).mockReturnValue({
    data,
    error: null,
    isPending: false,
  } as unknown as ReturnType<typeof useGetNumberPoolDivisions>);

const threeDevices: NumberPoolDivisions = {
  fields: ["device"],
  divisions: [
    deviceDivision("leaf10", 80),
    deviceDivision("Leaf2", 40),
    deviceDivision("spine1", 10),
  ],
};

const rowLabels = (component: Awaited<ReturnType<typeof render>>) =>
  component
    .getByRole("link")
    .elements()
    .map((link) => link.querySelector("[title]")?.getAttribute("title"));

const renderCard = (search = "") => {
  window.history.replaceState(null, "", `/resource-manager/${pool.id}${search}`);
  return render(
    <div className="flex h-125 flex-col">
      <NumberPoolDivisionsList pool={pool} />
    </div>
  );
};

describe("NumberPoolDivisionsList", () => {
  beforeEach(() => {
    store.set(nodeSchemasAtom, [interfaceSchema]);
  });

  afterEach(async () => {
    // the card re-renders when the address changes, so it must be gone before the mocks are reset
    await cleanup();
    window.history.replaceState(null, "", initialUrl);
    vi.resetAllMocks();
    store.set(nodeSchemasAtom, initialNodeSchemas);
  });

  it("lists the allocation scopes by usage, highest first, with their count", async () => {
    // GIVEN
    mockDivisions(threeDevices);

    // WHEN
    const component = await renderCard();

    // THEN
    await expect
      .element(component.getByRole("heading", { name: "Allocation scopes" }))
      .toBeVisible();
    await expect.element(component.getByText("3", { exact: true })).toBeVisible();
    expect(rowLabels(component)).toEqual(["leaf10", "Leaf2", "spine1"]);
  });

  it("keeps the allocation scopes whose values contain the search, ignoring case", async () => {
    // GIVEN
    mockDivisions(threeDevices);
    const component = await renderCard();

    // WHEN
    await userEvent.fill(component.getByRole("searchbox"), "LEAF");

    // THEN
    await expect.element(component.getByText("2 of 3")).toBeVisible();
    expect(rowLabels(component)).toEqual(["leaf10", "Leaf2"]);
  });

  it("sorts by a field in numeric-aware order", async () => {
    // GIVEN
    mockDivisions(threeDevices);
    const component = await renderCard();

    // WHEN
    await userEvent.click(component.getByRole("button", { name: "Device" }));

    // THEN
    await expect.element(component.getByRole("link").first()).toHaveTextContent("Leaf2");
    expect(rowLabels(component)).toEqual(["Leaf2", "leaf10", "spine1"]);
  });

  it("explains that a pool with no allocated numbers has no allocation scope yet", async () => {
    // GIVEN
    mockDivisions({ fields: ["device"], divisions: [] });

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByText("No numbers allocated yet.")).toBeVisible();
  });

  it("says when no allocation scope matches the search", async () => {
    // GIVEN
    mockDivisions(threeDevices);

    // WHEN
    const component = await renderCard("?allocation_scope_search=nothing");

    // THEN
    await expect.element(component.getByText("No allocation scope matches")).toBeVisible();
  });

  it("lists every allocation scope of a large pool", async () => {
    // GIVEN
    mockDivisions(generateNumberPoolDivisions({ fields: ["device"], count: 1000 }));

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByText("1,000", { exact: true })).toBeVisible();
    const lastRow = component.getByRole("link", { name: "device-1000" });
    lastRow.element().scrollIntoView();
    await expect.element(lastRow).toBeInViewport();
  });
});
