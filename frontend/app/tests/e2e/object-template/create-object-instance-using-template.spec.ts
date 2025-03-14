import { expect, test } from "@playwright/test";
import { ACCOUNT_STATE_PATH } from "../../constants";
import { saveScreenshotForDocs } from "../../utils";

test.describe("object-template", () => {
    test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });

    test.describe.fixme("object-template diff data", () => {
        test.describe.configure({ mode: "serial" });
        test.use({ storageState: ACCOUNT_STATE_PATH.ADMIN });
        test.slow();

        test.beforeEach(async function ({ page }) {
            page.on("response", async (response) => {
                if (response.status() === 500) {
                    await expect(response.url()).toBe("This URL responded with a 500 status");
                }
            });
        });
    })

    test('see-existig-template', async ({ page }) => {
        await page.goto("/objects/CoreObjectTemplate");
        await expect(page.getByTestId('create-object-button')).toBeVisible();
        await saveScreenshotForDocs(page, "template_list");
    });

    test('create-patch-panel-using-template', async ({ page }) => {
        await page.goto("/objects/InfraPatchPanel");
        await expect(page.getByTestId('create-object-button')).toBeVisible();
        await page.getByTestId('create-object-button').click();
        await expect(page.getByRole('button', { name: 'Start from template Pick a' })).toBeVisible();
        await saveScreenshotForDocs(page, "template_or_from_scratch");
        await page.getByRole('button', { name: 'Start from template Pick a' }).click();
        await page.getByRole('option', { name: 'Regular_Patch_Panel' }).click();
        await page.getByLabel('Name *').fill('patch-panel');
        await saveScreenshotForDocs(page, "form_with_template");
        await page.getByRole('button', { name: 'Save' }).click();
    });

    test('see-created-patch-panel', async ({ page }) => {
        await page.goto("/objects/InfraPatchPanel");
        await expect(page.getByTestId('create-object-button')).toBeVisible();
        await page.getByTestId('identifier-cell').first().click();
        await expect(page.getByText('Front Interfaces6')).toBeVisible();
        await saveScreenshotForDocs(page, "object_created_using_template");
        await page.getByText('Front Interfaces6').click();
        await expect(page.getByText('patch-panel, C1.P01')).toBeVisible();
        await saveScreenshotForDocs(page, "object_components_created_using_template");
    });
});