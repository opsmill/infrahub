import { expect, test } from "@playwright/test";

import { ACCOUNT_STATE_PATH } from "../../constants";
import { generateRandomBranchName, getDataTableRow } from "../../utils";
import { createBranchAPI, deleteBranchAPI } from "../utils/graphql";
import { loadSchemaAPI } from "../utils/schema";

const BRANCH_NAME = generateRandomBranchName("bare-address-");

const OBJECT_KIND = "TestingDnsRecord";

// One kind carrying both IPHost flavours side by side. `dns_target` refuses a prefix, so it holds a
// bare address; `mgmt_ip` declares nothing and keeps the host/prefix behaviour every existing
// schema relies on. The undeclared attribute is the control: without it a regression that strips
// masks everywhere would still pass.
const SCHEMA = {
  version: "1.0",
  nodes: [
    {
      name: "DnsRecord",
      namespace: "Testing",
      label: "DNS Record",
      include_in_menu: false,
      display_labels: ["dns_target__value"],
      human_friendly_id: ["dns_target__value"],
      attributes: [
        {
          name: "dns_target",
          label: "DNS Target",
          kind: "IPHost",
          unique: true,
          order_weight: 1000,
          parameters: { allow_prefix: false },
        },
        {
          name: "mgmt_ip",
          label: "Management IP",
          kind: "IPHost",
          optional: true,
          order_weight: 2000,
        },
      ],
    },
  ],
};

const BARE_ADDRESS = "10.0.0.1";
const BARE_ADDRESS_WITH_HOST_MASK = `${BARE_ADDRESS}/32`;
const PREFIXED_ADDRESS = "192.0.2.10/24";

test.describe("/objects/TestingDnsRecord - address attribute that refuses a prefix", () => {
  test.describe.configure({ mode: "serial" });
  test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

  test.beforeAll(async ({ request }) => {
    test.setTimeout(6 * 60 * 1000);
    await createBranchAPI(request, BRANCH_NAME);
    await loadSchemaAPI(request, BRANCH_NAME, SCHEMA);
  });

  test.afterAll(async ({ request }) => {
    await deleteBranchAPI(request, BRANCH_NAME);
  });

  test.beforeEach(async ({ page }) => {
    page.on("response", async (response) => {
      if (response.status() === 500) {
        await expect(response.url()).toBe("This URL responded with a 500 status");
      }
    });
  });

  test("stores and renders a redundant host mask as a bare address", async ({ page }) => {
    const form = page.getByLabel("sheet");

    await test.step("open the creation form", async () => {
      await page.goto(`/objects/${OBJECT_KIND}?branch=${BRANCH_NAME}`);
      await page.getByTestId("create-object-button").click();
      await expect(form.getByRole("heading", { name: "Create DNS Record" })).toBeVisible();
    });

    await test.step("assert the form offers no prefix-length control", async () => {
      // Both addresses are entered through a single free-text control. Nothing in the form lets an
      // operator supply a prefix length separately, for either flavour of the attribute.
      await expect(form.getByLabel("DNS Target *")).toBeVisible();
      await expect(form.getByLabel("Management IP")).toBeVisible();
      await expect(form.getByLabel(/prefix/i)).toHaveCount(0);
      await expect(form.getByLabel(/mask/i)).toHaveCount(0);
      await expect(form.getByRole("spinbutton")).toHaveCount(0);
    });

    await test.step("create the object", async () => {
      await form.getByLabel("DNS Target *").fill(BARE_ADDRESS_WITH_HOST_MASK);
      await form.getByLabel("Management IP").fill(PREFIXED_ADDRESS);
      await form.getByRole("button", { name: "Save" }).click();

      await expect(
        // The toast id is built from the schema name (not the kind) and carries the created node's
        // uuid suffix, so prefix-match it.
        page.locator('[id^="alert-success-DnsRecord-created"]')
      ).toBeVisible();
    });

    await test.step("assert the list view shows no mask on the bare address", async () => {
      const row = getDataTableRow(page, BARE_ADDRESS);
      await expect(row).toBeVisible();
      await expect(row).toContainText(PREFIXED_ADDRESS);
      await expect(row).not.toContainText(BARE_ADDRESS_WITH_HOST_MASK);
    });
  });

  test("shows the bare address in the detail view, the display label and the edit form", async ({
    page,
  }) => {
    await test.step("open the object from the list view", async () => {
      await page.goto(`/objects/${OBJECT_KIND}?branch=${BRANCH_NAME}`);
      await page.getByRole("link", { name: BARE_ADDRESS, exact: true }).click();
    });

    await test.step("assert the detail view keeps each attribute's own notation", async () => {
      const details = page.getByTestId("object-details");
      await expect(details.getByText(`DNS Target${BARE_ADDRESS}`)).toBeVisible();
      await expect(details.getByText(`Management IP${PREFIXED_ADDRESS}`)).toBeVisible();
      await expect(details).not.toContainText(BARE_ADDRESS_WITH_HOST_MASK);
    });

    await test.step("assert the display label carries no mask", async () => {
      const breadcrumb = page.getByTestId("breadcrumb-navigation");
      await expect(breadcrumb).toContainText(BARE_ADDRESS);
      await expect(breadcrumb).not.toContainText(BARE_ADDRESS_WITH_HOST_MASK);
    });

    await test.step("assert the edit form pre-fills the bare address", async () => {
      await page.getByTestId("edit-button").click();

      const form = page.getByLabel("sheet");
      await expect(form.getByLabel("DNS Target *")).toHaveValue(BARE_ADDRESS);
      await expect(form.getByLabel("Management IP")).toHaveValue(PREFIXED_ADDRESS);
      await expect(form.getByLabel(/prefix/i)).toHaveCount(0);
      await expect(form.getByRole("spinbutton")).toHaveCount(0);
    });
  });

  test("surfaces an error naming the attribute when a subnet prefix is submitted", async ({
    page,
  }) => {
    await page.goto(`/objects/${OBJECT_KIND}?branch=${BRANCH_NAME}`);
    await page.getByTestId("create-object-button").click();

    const form = page.getByLabel("sheet");
    await form.getByLabel("DNS Target *").fill("10.0.0.9/24");
    await form.getByRole("button", { name: "Save" }).click();

    const errorAlert = page.locator("#alert-error");
    await expect(errorAlert).toContainText("subnet prefix is not permitted");
    await expect(errorAlert).toContainText("dns_target");
  });
});
