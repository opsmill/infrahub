import { focusManager } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { getAppInfo } from "@/entities/config/domain/use-cases/get-app-info";
import { useGetAppInfo } from "@/entities/config/ui/queries/get-app-info.query";

import { render } from "../../../../../tests/components/render";
import { generateLicenseInfoWithoutLicense } from "../../../../../tests/fake/license";

vi.mock("@/entities/config/domain/use-cases/get-app-info");

const ONE_HOUR_MS = 60 * 60 * 1000;

function AppVersion() {
  const { data } = useGetAppInfo();
  return <span>{data ? `v${data.version}` : "loading"}</span>;
}

function answerVersions(first: string, next: string) {
  const appInfo = (version: string) => ({
    version,
    deployment_id: "abc-123-def",
    license: generateLicenseInfoWithoutLicense(),
  });
  vi.mocked(getAppInfo).mockResolvedValueOnce(appInfo(first)).mockResolvedValue(appInfo(next));
}

beforeEach(() => {
  answerVersions("1.12.0", "1.12.1");
});

afterEach(() => {
  vi.useRealTimers();
  focusManager.setFocused(undefined);
  vi.clearAllMocks();
});

describe("useGetAppInfo", () => {
  test("refreshes the app info every hour", async () => {
    // GIVEN
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
    const component = await render(<AppVersion />);
    await expect.element(component.getByText("v1.12.0")).toBeVisible();

    // WHEN
    vi.advanceTimersByTime(ONE_HOUR_MS);

    // THEN
    await expect.element(component.getByText("v1.12.1")).toBeVisible();
  });

  test("refreshes the app info whenever the window regains focus, even while it is fresh", async () => {
    // GIVEN
    const component = await render(<AppVersion />);
    await expect.element(component.getByText("v1.12.0")).toBeVisible();
    focusManager.setFocused(false);

    // WHEN
    focusManager.setFocused(true);

    // THEN
    await expect.element(component.getByText("v1.12.1")).toBeVisible();
  });
});
