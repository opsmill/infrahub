/// <reference types="cypress" />

import { ADMIN_CREDENTIALS, SCREENSHOT_ENV_VARIABLE, screenshotConfig } from "../../utils";

const DEVICE_NAME = "atl1-edge1";

describe("Tutorial - Part 4", () => {
  beforeEach(function () {
    cy.login(ADMIN_CREDENTIALS.username, ADMIN_CREDENTIALS.password);

    cy.visit("/");

    this.screenshots = Cypress.env(SCREENSHOT_ENV_VARIABLE);
  });

  it("should verify the metadata from the demo dataset", function () {
    // Access to the devices
    cy.get("[href='/objects/InfraDevice'] > .group").click();

    // Click on a device
    cy.contains(DEVICE_NAME).click();

    cy.get(".sm\\:p-0 > :nth-child(1)").within(() => {
      // Click to open the metadata for the name
      cy.contains("Name")
        .parent()
        .within(() => {
          cy.get("[data-cy='metadata-button']").click();
        });

      cy.get(":nth-child(4) > .underline").should("have.text", "Pop-Builder");

      if (this.screenshots) {
        cy.screenshot("tutorial_4_metadata", screenshotConfig);
      }

      // Click to open the edit panel
      cy.get(".w-80 > :nth-child(1) > .rounded-md").click();
    });

    cy.get(":nth-child(1) > .grid > .sm\\:col-span-6 > .block").should("exist");

    if (this.screenshots) {
      cy.screenshot("tutorial_4_metadata_edit", screenshotConfig);
    }

    cy.get("[data-cy='side-panel-background']").click(); // Close the popin

    // Click to open the metadata for the role
    cy.get(".sm\\:p-0 > :nth-child(1)").within(() => {
      cy.contains("Role")
        .parent()
        .within(() => {
          cy.get("[data-cy='metadata-button']").click();
        });

      cy.get(":nth-child(5) > .underline").should("have.text", "Engineering Team");
    });

    cy.contains(DEVICE_NAME).first().click(); // Close the popin

    cy.get(".sm\\:p-0 > :nth-child(1)").within(() => {
      // Click to open the metadata for a tag
      cy.get(":nth-child(1) > .p-2").click();
    });

    cy.get("[data-cy='metadata-tooltip']").within(() => {
      cy.contains("Is protected")
        .parent()
        .within(() => {
          cy.contains("False").should("exist");
        });
    });

    cy.contains(DEVICE_NAME).first().click(); // Close the popin
  });
});
