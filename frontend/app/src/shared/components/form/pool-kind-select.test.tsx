import { describe, expect, test, vi } from "vitest";

import { PoolKindSelect } from "@/shared/components/form/pool-kind-select";

import { render } from "../../../../tests/components/render";

const options = [
  { kind: "IpamIPAddress", label: "Ipam IP Address", namespace: "Ipam" },
  { kind: "TestIPAddress", label: "Test IP Address", namespace: "Test" },
];

describe("PoolKindSelect", () => {
  test("renders the selected kind with its namespace", async () => {
    const component = await render(
      <PoolKindSelect value="TestIPAddress" options={options} onChange={() => {}} />
    );

    await expect.element(component.getByLabelText("Type to allocate")).toBeVisible();
    await expect
      .element(component.getByTestId("pool-kind-select"))
      .toHaveTextContent("Test IP Address");
    await expect.element(component.getByTestId("pool-kind-select")).toHaveTextContent("Test");
  });

  test("shows the pool default kind as a placeholder when nothing overrides it", async () => {
    const component = await render(
      <PoolKindSelect
        value={undefined}
        options={options}
        placeholder="Ipam IP Address"
        onChange={() => {}}
      />
    );

    await expect
      .element(component.getByTestId("pool-kind-select"))
      .toHaveTextContent("Ipam IP Address");
  });

  test("lists every option with its namespace", async () => {
    const component = await render(
      <PoolKindSelect value={null} options={options} onChange={() => {}} />
    );

    await component.getByTestId("pool-kind-select").click();

    await expect
      .element(component.getByRole("option", { name: /Ipam IP Address/ }))
      .toHaveTextContent("Ipam");
    await expect
      .element(component.getByRole("option", { name: /Test IP Address/ }))
      .toHaveTextContent("Test");
  });

  test("emits the picked kind", async () => {
    const onChange = vi.fn<(kind: string | null) => void>();
    const component = await render(
      <PoolKindSelect value={null} options={options} onChange={onChange} />
    );

    await component.getByTestId("pool-kind-select").click();
    await component.getByRole("option", { name: /Test IP Address/ }).click();

    expect(onChange).toHaveBeenLastCalledWith("TestIPAddress");
  });

  test("emits null when the selected kind is cleared (so the pool default applies again)", async () => {
    const onChange = vi.fn<(kind: string | null) => void>();
    const component = await render(
      <PoolKindSelect value="TestIPAddress" options={options} onChange={onChange} />
    );

    await component.getByTestId("pool-kind-select").click();
    await component.getByRole("option", { name: /Test IP Address/ }).click();

    expect(onChange).toHaveBeenLastCalledWith(null);
  });

  test("marks itself invalid when told to", async () => {
    const component = await render(
      <PoolKindSelect value={null} options={options} invalid onChange={() => {}} />
    );

    await expect.element(component.getByTestId("pool-kind-select")).toHaveClass("border-danger");
  });
});
