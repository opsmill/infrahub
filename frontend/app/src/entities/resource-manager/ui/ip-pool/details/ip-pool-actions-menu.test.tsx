import { describe, expect, it } from "vitest";

import type { IpPoolData } from "@/entities/resource-manager/domain/model/ip-pool";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

import { render } from "../../../../../../tests/components/render";
import {
  generateIpAddressPoolData,
  generateIpPrefixPoolData,
} from "../../../../../../tests/fake/ip-pool";
import { generatePermission } from "../../../../../../tests/fake/permission";
import { generateNodeSchema } from "../../../../../../tests/fake/schema";
import { IpPoolActionsMenu } from "./ip-pool-actions-menu";

const prefixPoolSchema = generateNodeSchema({ kind: "CoreIPPrefixPool", documentation: null });

const openMenu = async ({
  pool,
  schema = prefixPoolSchema,
}: {
  pool: IpPoolData;
  schema?: ModelSchema;
}) => {
  const component = await render(
    <IpPoolActionsMenu pool={pool} schema={schema} permission={generatePermission()} />
  );
  await component.getByRole("button", { name: "Actions" }).click();
  return component;
};

describe("IpPoolActionsMenu", () => {
  it("links to the prefix pool schema", async () => {
    // GIVEN
    const pool = generateIpPrefixPoolData();

    // WHEN
    const component = await openMenu({ pool });

    // THEN
    await expect
      .element(component.getByRole("menuitem", { name: "View schema" }))
      .toHaveAttribute("href", expect.stringContaining("kind=CoreIPPrefixPool"));
  });

  it("links to the address pool schema for an address pool", async () => {
    // GIVEN
    const pool = generateIpAddressPoolData();
    const schema = generateNodeSchema({ kind: "CoreIPAddressPool", documentation: null });

    // WHEN
    const component = await openMenu({ pool, schema });

    // THEN
    await expect
      .element(component.getByRole("menuitem", { name: "View schema" }))
      .toHaveAttribute("href", expect.stringContaining("kind=CoreIPAddressPool"));
  });
});
