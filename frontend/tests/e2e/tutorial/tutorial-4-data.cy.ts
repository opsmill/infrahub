/// <reference types="cypress" />

import { ADMIN_CREDENTIALS, SCREENSHOT_ENV_VARIABLE, screenshotConfig } from "../utils";

describe("Tutorial - Part 4", () => {
  beforeEach(function () {
    cy.login(ADMIN_CREDENTIALS.username, ADMIN_CREDENTIALS.password);

    cy.visit("/");

    this.screenshots = Cypress.env(SCREENSHOT_ENV_VARIABLE);
  });

  it("should verify the metadata from the demo dataset", function () {
    // Access to the devices
    cy.get("[href='/objects/Device'] > .group").click();

    // Click on a device
    cy.contains("atl1-edge1").click();

    // Click to open the metadata for the name
    cy.get(":nth-child(2) > div.items-center > .p-2").click();
    cy.get(":nth-child(4) > .underline").should("have.text", "Pop-Builder");

    if (this.screenshots) {
      cy.screenshot("tutorial_4_metadata", screenshotConfig);
    }

    // Click to open the edit panel
    cy.get(".w-80 > :nth-child(1) > .rounded-md").click();

    cy.get(":nth-child(1) > .grid > .sm\\:col-span-6 > .block").should("exist");

    if (this.screenshots) {
      cy.screenshot("tutorial_4_metadata_edit", screenshotConfig);
    }

    cy.get(".bg-gray-500").click(); // Close the popin

    // Click to open the metadata for the role
    cy.get(":nth-child(7) > .py-4 > .mt-1 > .p-2").click();
    cy.get(":nth-child(5) > .underline").should("have.text", "Engineering Team");
    cy.get(".px-4.sm\\:px-6").click(); // Close the popin

    // Click to open the metadata for a tag
    cy.get(":nth-child(1) > .p-2").click();
    cy.get(":nth-child(5) > :nth-child(2)").should("have.text", "False");
    cy.get(".px-4.sm\\:px-6").click(); // Close the popin
  });
});
