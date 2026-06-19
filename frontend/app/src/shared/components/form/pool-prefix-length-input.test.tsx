import { describe, expect, test, vi } from "vitest";

import { PoolPrefixLengthInput } from "@/shared/components/form/pool-prefix-length-input";

import { render } from "../../../../tests/components/render";

describe("PoolPrefixLengthInput", () => {
  test("renders the prefilled prefix length", async () => {
    const component = await render(<PoolPrefixLengthInput value={32} onChange={() => {}} />);

    await expect.element(component.getByLabelText("Prefix length")).toBeVisible();
    await expect.element(component.getByTestId("pool-prefix-length-input")).toHaveValue("32");
  });

  test("renders empty when there is no value", async () => {
    const component = await render(<PoolPrefixLengthInput value={undefined} onChange={() => {}} />);

    await expect.element(component.getByTestId("pool-prefix-length-input")).toHaveValue("");
  });

  test("emits the entered number", async () => {
    const onChange = vi.fn<(value: number | null) => void>();
    const component = await render(<PoolPrefixLengthInput value={undefined} onChange={onChange} />);

    await component.getByTestId("pool-prefix-length-input").fill("28");

    expect(onChange).toHaveBeenLastCalledWith(28);
  });

  test("emits null when cleared (so the empty state is written, not a no-op)", async () => {
    const onChange = vi.fn<(value: number | null) => void>();
    const component = await render(<PoolPrefixLengthInput value={28} onChange={onChange} />);

    await component.getByTestId("pool-prefix-length-input").fill("");

    expect(onChange).toHaveBeenLastCalledWith(null);
  });
});
