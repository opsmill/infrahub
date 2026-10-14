import { afterEach, describe, expect, it, vi } from "vitest";
import { userEvent } from "vitest/browser";
import { cleanup } from "vitest-browser-react";

import { useGetNumberPoolDivisions } from "@/entities/resource-manager/ui/queries/get-number-pool-divisions.query";

import { render } from "../../../../../../tests/components/render";
import {
  generateNumberPoolData,
  generateNumberPoolDivision,
  generateNumberPoolDivisionEntry,
  generateNumberPoolUsage,
} from "../../../../../../tests/fake/number-pool";
import { NumberPoolDivisionCard } from "./number-pool-division-card";

vi.mock("@/entities/resource-manager/ui/queries/get-number-pool-divisions.query", () => ({
  useGetNumberPoolDivisions: vi.fn(),
}));

const initialUrl = window.location.href;

const pool = generateNumberPoolData({
  id: "pool-id",
  allocation_scope: { value: ["device", "role"] },
});

const selector = (device: string, role: string) => [
  { path: "device", value: device },
  { path: "role", value: role },
];

const division = (device: string, role: string, utilization: number) =>
  generateNumberPoolDivision({
    entries: [
      generateNumberPoolDivisionEntry({ path: "device", value: `${device}-id`, label: device }),
      generateNumberPoolDivisionEntry({ path: "role", value: role, label: role, peerKind: null }),
    ],
    usage: generateNumberPoolUsage({ utilization }),
  });

const mockDivisions = () =>
  vi.mocked(useGetNumberPoolDivisions).mockReturnValue({
    data: {
      fields: ["device", "role"],
      divisions: [division("atl1-core1", "leaf", 20), division("den1-edge2", "spine", 80)],
    },
  } as unknown as ReturnType<typeof useGetNumberPoolDivisions>);

describe("NumberPoolDivisionCard", () => {
  afterEach(async () => {
    // the card re-renders when the address changes, so it must be gone before the mocks are reset
    await cleanup();
    window.history.replaceState(null, "", initialUrl);
    vi.resetAllMocks();
  });

  it("shows the labels of the open allocation scope in the selector", async () => {
    // GIVEN
    mockDivisions();

    // WHEN
    const component = await render(
      <NumberPoolDivisionCard pool={pool} division={selector("atl1-core1-id", "leaf")} />
    );

    // THEN
    await expect
      .element(component.getByRole("button", { name: /Allocation scope/ }))
      .toHaveTextContent(/atl1-core1 · leaf/);
  });

  it("shows the raw values of an allocation scope that holds no numbers", async () => {
    // GIVEN
    mockDivisions();

    // WHEN
    const component = await render(
      <NumberPoolDivisionCard pool={pool} division={selector("other-id", "spine")} />
    );

    // THEN
    await expect
      .element(component.getByRole("button", { name: /Allocation scope/ }))
      .toHaveTextContent(/other-id · spine/);
  });

  it("lists the fullest allocation scope first", async () => {
    // GIVEN
    mockDivisions();
    const component = await render(
      <NumberPoolDivisionCard pool={pool} division={selector("atl1-core1-id", "leaf")} />
    );

    // WHEN
    await userEvent.click(component.getByRole("button", { name: /Allocation scope/ }));

    // THEN
    const options = component.getByRole("option");
    await expect.element(options.first()).toHaveTextContent(/den1-edge2 · spine.*80%/);
    await expect.element(options.last()).toHaveTextContent(/atl1-core1 · leaf.*20%/);
  });

  it("opens the allocation scope the operator picks", async () => {
    // GIVEN
    mockDivisions();
    const component = await render(
      <NumberPoolDivisionCard pool={pool} division={selector("atl1-core1-id", "leaf")} />
    );
    await userEvent.click(component.getByRole("button", { name: /Allocation scope/ }));

    // WHEN
    await userEvent.click(component.getByRole("option", { name: /den1-edge2/ }));

    // THEN
    expect(new URLSearchParams(window.location.search).get("allocation_scope")).toBe(
      JSON.stringify(["den1-edge2-id", "spine"])
    );
  });

  it("links back to every allocation scope of the pool", async () => {
    // GIVEN
    mockDivisions();

    // WHEN
    const component = await render(
      <NumberPoolDivisionCard pool={pool} division={selector("atl1-core1-id", "leaf")} />
    );

    // THEN
    await expect
      .element(component.getByRole("link", { name: "All allocation scopes" }))
      .toHaveAttribute("href", expect.stringMatching(/^\/resource-manager\/pool-id(\?|$)/));
  });
});
