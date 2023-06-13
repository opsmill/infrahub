/// <reference types="cypress" />

import { SCREENSHOT_ENV_VARIABLE, screenshotConfig } from "../utils";

describe("Tutorial - Part 4", () => {
  beforeEach(function () {
    cy.visit("/");
    this.screenshots = Cypress.env(SCREENSHOT_ENV_VARIABLE);
  });

  it("should verify the metadata from the demo dataset", function () {
    // Access to the devices
    cy.get("[href='/objects/device'] > .group").click();

    // Click on a device
    cy.contains("atl1-edge1").click();

    // Click to open the metadata for the name
    cy.get(".sm\\:p-0 > :nth-child(1) > :nth-child(2) > div.items-center > .relative").click();
    cy.get(":nth-child(4) > .underline").should("have.text", "Pop-Builder");

    if (this.screenshots) {
      cy.screenshot("tutorial_4_metadata", screenshotConfig);
    }

    // Click to open the edit panel
    cy.get(".cursor-pointer > .w-5").click();

    if (this.screenshots) {
      cy.screenshot("tutorial_4_metadata_edit", screenshotConfig);
    }

    cy.get(".bg-gray-500").click(); // Close the popin

    // Click to open the metadata for the role
    cy.get(":nth-child(7) > .py-4 > .mt-1 > .relative").click();
    cy.get(":nth-child(5) > .underline").should("have.text", "Engineering Team");
    cy.get(":nth-child(7) > .py-4 > .mt-1 > .relative").click(); // Close the popin

    // Click to open the metadata for a tag
    cy.get(".sm\\:col-span-2 > :nth-child(1) > .relative").click();
    cy.get(":nth-child(5) > :nth-child(2)").should("have.text", "False");
    cy.get(".sm\\:col-span-2 > :nth-child(1) > .relative").click(); // Close the popin
  });
});
