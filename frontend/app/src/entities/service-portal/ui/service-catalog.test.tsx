import { beforeEach, describe, expect, test, vi } from "vitest";

import type { ServiceCatalogEntry } from "@/entities/service-portal/domain/model/service-catalog";
import { getServiceCatalog } from "@/entities/service-portal/domain/use-cases/get-service-catalog";

import { render } from "../../../../tests/components/render";
import { ServiceCatalog } from "./service-catalog";

vi.mock("@/entities/service-portal/domain/use-cases/get-service-catalog");

const buildEntry = (overrides: Partial<ServiceCatalogEntry>): ServiceCatalogEntry => ({
  id: "entry-1",
  name: "Layer 2 VPN",
  description: "A point-to-point link between two sites",
  icon: "mdi:lan",
  tags: [],
  target_kind: "ServiceL2Vpn",
  mode: "review",
  fields: ["name"],
  generators: [],
  template_id: null,
  ...overrides,
});

describe("ServiceCatalog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("renders one card per returned entry with name, description, icon and tags", async () => {
    vi.mocked(getServiceCatalog).mockResolvedValue([
      buildEntry({ id: "entry-1", tags: ["network", "gold"] }),
      buildEntry({
        id: "entry-2",
        name: "Virtual machine",
        description: "A Linux VM",
        icon: "mdi:server",
        tags: ["compute"],
      }),
    ]);

    const component = await render(<ServiceCatalog />);

    await expect
      .element(component.getByRole("link", { name: /Layer 2 VPN/ }))
      .toHaveAttribute("href", "/service-portal/entries/entry-1");
    expect(component.getByRole("listitem").all()).toHaveLength(2);

    const vpnCard = component.getByRole("listitem").nth(0);
    const vmCard = component.getByRole("listitem").nth(1);
    await expect
      .element(vpnCard.getByText("A point-to-point link between two sites"))
      .toBeVisible();
    await expect.element(vpnCard.getByText("network")).toBeVisible();
    await expect.element(vpnCard.getByText("gold")).toBeVisible();
    expect(vpnCard.element().querySelector("iconify-icon")?.getAttribute("icon")).toBe("mdi:lan");

    await expect.element(vmCard.getByText("Virtual machine")).toBeVisible();
    await expect.element(vmCard.getByText("A Linux VM")).toBeVisible();
    await expect.element(vmCard.getByText("compute")).toBeVisible();
    expect(vmCard.element().querySelector("iconify-icon")?.getAttribute("icon")).toBe("mdi:server");
    await expect
      .element(vmCard.getByRole("link"))
      .toHaveAttribute("href", "/service-portal/entries/entry-2");
  });

  test("renders the empty state when the catalog has no entries", async () => {
    vi.mocked(getServiceCatalog).mockResolvedValue([]);

    const component = await render(<ServiceCatalog />);

    await expect.element(component.getByText("No data")).toBeVisible();
    await expect.element(component.getByText(/No services are available yet/)).toBeVisible();
    expect(component.getByRole("listitem").all()).toHaveLength(0);
  });
});
