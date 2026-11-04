import { afterEach, describe, expect, it } from "vitest";
import { userEvent } from "vitest/browser";

import { ReactAriaRouterProvider } from "@/app/providers/react-aria-router-provider";

import { IP_ADDRESS_POOL, IP_PREFIX_POOL } from "@/entities/resource-manager/domain/model/pool";

import { render } from "../../../../../../tests/components/render";
import { generateIpPoolResource } from "../../../../../../tests/fake/ip-pool";
import { IpPoolResourcesCard, type IpPoolResourcesCardProps } from "./ip-pool-resources-card";

const initialPath = window.location.pathname;

const firstResource = generateIpPoolResource({
  id: "18a3c2f1-0000-4000-8000-0000000000r1",
  display_label: "10.10.0.0/22",
  allocationWeight: 100,
});
const secondResource = generateIpPoolResource({
  id: "18a3c2f1-0000-4000-8000-0000000000r2",
  display_label: "10.10.4.0/22",
  allocationWeight: 50,
});
const resources = [firstResource, secondResource];

const renderCard = (props: Partial<IpPoolResourcesCardProps> = {}) =>
  render(
    <ReactAriaRouterProvider>
      <IpPoolResourcesCard
        poolId="pool-id"
        poolKind={IP_PREFIX_POOL}
        resources={resources}
        selectedResourceId={null}
        {...props}
      />
    </ReactAriaRouterProvider>
  );

describe("IpPoolResourcesCard", () => {
  afterEach(() => {
    window.history.replaceState(null, "", initialPath);
  });

  it("lists the resource prefixes in the given order with their weight", async () => {
    // GIVEN
    const props = { resources };

    // WHEN
    const component = await renderCard(props);

    // THEN
    const options = component.getByRole("option").elements();
    expect(options.map((option) => option.textContent)).toEqual([
      expect.stringContaining("10.10.0.0/22Weight 100"),
      expect.stringContaining("10.10.4.0/22Weight 50"),
    ]);
  });

  it("shows no weight when the resource prefixes have none", async () => {
    // GIVEN
    const unweightedResources = resources.map((resource) =>
      generateIpPoolResource({ ...resource, allocationWeight: null })
    );

    // WHEN
    const component = await renderCard({ resources: unweightedResources });

    // THEN
    const options = component.getByRole("option").elements();
    expect(options).toHaveLength(2);
    expect(options.some((option) => option.textContent?.includes("Weight"))).toBe(false);
  });

  it("keeps the weight of a long IPv6 resource prefix", async () => {
    // GIVEN
    const longResource = generateIpPoolResource({
      display_label: "2001:0db8:85a3:0000:0000:8a2e:0370:0000/112",
      allocationWeight: 10,
    });

    // WHEN
    const component = await renderCard({ resources: [longResource] });

    // THEN
    await expect
      .element(component.getByText("2001:0db8:85a3:0000:0000:8a2e:0370:0000/112"))
      .toBeInTheDocument();
    await expect.element(component.getByText("Weight 10")).toBeVisible();
  });

  it("selects the resource prefix named in the address", async () => {
    // GIVEN
    const selectedResourceId = secondResource.id;

    // WHEN
    const component = await renderCard({ selectedResourceId });

    // THEN
    await expect
      .element(component.getByRole("option", { name: /^10\.10\.4\.0\/22/ }))
      .toHaveAttribute("aria-selected", "true");
  });

  it("selects nothing for a resource prefix that is not in the pool", async () => {
    // GIVEN
    const selectedResourceId = "not-in-pool";

    // WHEN
    const component = await renderCard({ selectedResourceId });

    // THEN
    const options = component.getByRole("option").elements();
    expect(options).toHaveLength(2);
    expect(
      options.filter((option) => option.getAttribute("aria-selected") === "true")
    ).toHaveLength(0);
  });

  it("opens the next resource prefix with the arrow and Enter keys", async () => {
    // GIVEN
    await renderCard({ selectedResourceId: firstResource.id });
    await userEvent.keyboard("{Tab}");

    // WHEN
    await userEvent.keyboard("{ArrowDown}{Enter}");

    // THEN
    await expect
      .poll(() => window.location.pathname)
      .toBe(`/resource-manager/pool-id/resources/${secondResource.id}`);
  });

  it("asks to edit the prefix pool when it has no resource prefix", async () => {
    // GIVEN
    const props: Partial<IpPoolResourcesCardProps> = { poolKind: IP_PREFIX_POOL, resources: [] };

    // WHEN
    const component = await renderCard(props);

    // THEN
    await expect.element(component.getByText("No resource prefixes")).toBeVisible();
    await expect
      .element(
        component.getByText("This pool can't allocate prefixes until it has a resource prefix.")
      )
      .toBeVisible();
    await expect.element(component.getByText("Edit the pool to add one.")).toBeVisible();
  });

  it("names addresses in the empty state of an address pool", async () => {
    // GIVEN
    const props: Partial<IpPoolResourcesCardProps> = { poolKind: IP_ADDRESS_POOL, resources: [] };

    // WHEN
    const component = await renderCard(props);

    // THEN
    await expect
      .element(
        component.getByText("This pool can't allocate addresses until it has a resource prefix.")
      )
      .toBeVisible();
  });
});
