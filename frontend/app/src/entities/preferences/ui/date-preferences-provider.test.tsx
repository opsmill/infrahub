import React from "react";
import { beforeEach, describe, expect, test, vi } from "vitest";

import { DatePreferencesContext } from "@/shared/context/date-preferences-context";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import type { EffectivePreferences } from "@/entities/preferences/domain/model/preference";
import { dateFormatPattern } from "@/entities/preferences/domain/rules/date-format";
import { DatePreferencesProvider } from "@/entities/preferences/ui/date-preferences-provider";
import { useGetEffectivePreferences } from "@/entities/preferences/ui/queries/get-effective-preferences.query";

import { render } from "../../../../tests/components/render";

vi.mock("@/entities/preferences/ui/queries/get-effective-preferences.query");
vi.mock("@/entities/authentication/ui/auth-provider");

// Fixtures follow the `inherited` invariant documented on `EffectivePreference`.
function mockEffective(data: EffectivePreferences | undefined) {
  // The provider only reads `.data`; the rest of the query result is irrelevant here.
  vi.mocked(useGetEffectivePreferences).mockReturnValue({ data } as ReturnType<
    typeof useGetEffectivePreferences
  >);
}

function mockAuth(isAuthenticated: boolean) {
  vi.mocked(useAuth).mockReturnValue({ isAuthenticated } as ReturnType<typeof useAuth>);
}

/** Surfaces the resolved context so tests can assert what the provider computed. */
function Probe() {
  const resolved = React.use(DatePreferencesContext);
  return (
    <>
      <span data-testid="pattern">{resolved?.pattern ?? "null"}</span>
      <span data-testid="timezone">{resolved?.timezone ?? "null"}</span>
    </>
  );
}

async function renderWithEffective(data: EffectivePreferences | undefined) {
  mockEffective(data);
  return render(
    <DatePreferencesProvider>
      <Probe />
    </DatePreferencesProvider>
  );
}

describe("DatePreferencesProvider", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockAuth(true);
  });

  test("does not fetch for a logged-out user (anonymous access must not 401)", async () => {
    mockAuth(false);
    const component = await renderWithEffective(undefined);
    expect(useGetEffectivePreferences).not.toHaveBeenCalled();
    await expect.element(component.getByTestId("pattern")).toHaveTextContent("null");
    await expect.element(component.getByTestId("timezone")).toHaveTextContent("null");
  });

  test("fetches once authenticated", async () => {
    await renderWithEffective(undefined);
    expect(useGetEffectivePreferences).toHaveBeenCalled();
  });

  test("resolves the preferred pattern + timezone from a USER preference", async () => {
    const component = await renderWithEffective({
      dateFormat: {
        value: "EU_DATETIME",
        source: "USER",
        inherited: { value: null, source: "DEFAULT" },
      },
      timezone: {
        value: "Europe/Paris",
        source: "USER",
        inherited: { value: null, source: "DEFAULT" },
      },
    });

    await expect
      .element(component.getByTestId("pattern"))
      .toHaveTextContent(dateFormatPattern("EU_DATETIME"));
    await expect.element(component.getByTestId("timezone")).toHaveTextContent("Europe/Paris");
  });

  test("resolves an organisation (GLOBAL) default the same way", async () => {
    const component = await renderWithEffective({
      dateFormat: {
        value: "ISO_DATETIME",
        source: "GLOBAL",
        inherited: { value: "ISO_DATETIME", source: "GLOBAL" },
      },
      timezone: {
        value: "Asia/Tokyo",
        source: "GLOBAL",
        inherited: { value: "Asia/Tokyo", source: "GLOBAL" },
      },
    });

    await expect
      .element(component.getByTestId("pattern"))
      .toHaveTextContent(dateFormatPattern("ISO_DATETIME"));
    await expect.element(component.getByTestId("timezone")).toHaveTextContent("Asia/Tokyo");
  });

  test("resolves to null (browser fallback) when both fields are DEFAULT", async () => {
    const component = await renderWithEffective({
      dateFormat: { value: null, source: "DEFAULT", inherited: { value: null, source: "DEFAULT" } },
      timezone: { value: null, source: "DEFAULT", inherited: { value: null, source: "DEFAULT" } },
    });

    await expect.element(component.getByTestId("pattern")).toHaveTextContent("null");
    await expect.element(component.getByTestId("timezone")).toHaveTextContent("null");
  });

  test("stays null (browser fallback) while the query has no data yet", async () => {
    const component = await renderWithEffective(undefined);

    await expect.element(component.getByTestId("pattern")).toHaveTextContent("null");
    await expect.element(component.getByTestId("timezone")).toHaveTextContent("null");
  });
});
