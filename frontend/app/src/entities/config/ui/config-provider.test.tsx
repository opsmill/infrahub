import { useQueryClient } from "@tanstack/react-query";
import { afterEach, describe, expect, test, vi } from "vitest";

import { getConfig } from "@/entities/config/domain/use-cases/get-config";
import { ConfigProvider, useConfig } from "@/entities/config/ui/config-provider";
import { getConfigQueryOptions, useGetConfig } from "@/entities/config/ui/queries/get-config.query";

import { render } from "../../../../tests/components/render";
import { generateConfigWithInstance } from "../../../../tests/fake/config";

vi.mock("@/entities/config/domain/use-cases/get-config");

const Probe = () => {
  const config = useConfig();
  const { error } = useGetConfig();
  const queryClient = useQueryClient();

  return (
    <>
      <span>Instance: {config.instance.label}</span>
      {error && <span>Refetch error: {error.message}</span>}
      <button
        type="button"
        onClick={() => queryClient.refetchQueries({ queryKey: getConfigQueryOptions().queryKey })}
      >
        refetch
      </button>
    </>
  );
};

describe("ConfigProvider", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  test("keeps the loaded config on screen when a refetch fails", async () => {
    // GIVEN
    vi.mocked(getConfig)
      .mockResolvedValueOnce(generateConfigWithInstance("QA", null))
      .mockRejectedValueOnce(new Error("Network error"));
    const component = await render(
      <ConfigProvider>
        <Probe />
      </ConfigProvider>
    );
    await expect.element(component.getByText("Instance: QA")).toBeVisible();

    // WHEN
    await component.getByRole("button", { name: "refetch" }).click();

    // THEN
    await expect.element(component.getByText("Refetch error: Network error")).toBeVisible();
    await expect.element(component.getByText("Instance: QA")).toBeVisible();
  });

  test("shows the error when the first load fails", async () => {
    // GIVEN
    vi.mocked(getConfig).mockRejectedValue(new Error("Network error"));

    // WHEN
    const component = await render(
      <ConfigProvider>
        <Probe />
      </ConfigProvider>
    );

    // THEN
    await expect.element(component.getByText("Network error", { exact: true })).toBeVisible();
    expect(component.getByText("Instance: QA").query()).toBeNull();
  });
});
