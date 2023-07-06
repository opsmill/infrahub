/// <reference types="cypress" />

import { ADMIN_CREDENTIALS, SCREENSHOT_ENV_VARIABLE, screenshotConfig } from "../../utils";

const NEW_BRANCH = "update-ethernet1";
const DEVICE = "atl1-edge1";
const INTERFACE = "Ethernet12";
const NEW_INTERFACE_DESCRIPTION = "New description in the branch";

describe("Tutorial - Part 6", () => {
  beforeEach(function () {
    cy.login(ADMIN_CREDENTIALS.username, ADMIN_CREDENTIALS.password);

    cy.visit("/");

    this.screenshots = Cypress.env(SCREENSHOT_ENV_VARIABLE);
  });

  it("should create a new branch with a git integration", function () {
    // Open the branch creation form
    cy.get("#headlessui-popover-button-\\:r8\\: > .py-1\\.5").click();

    // Add the new branch name
    cy.get(".flex-col > :nth-child(1) > .block").type(NEW_BRANCH);

    // Toggle the data-only field
    cy.get(".px-1\\.5").within(() => {
      // Get the switch within the last row of the form
      cy.get("[role='switch']").click();

      // Remove focus from switch
      cy.get("[role='switch']").blur();
    });

    if (this.screenshots) {
      cy.screenshot("tutorial_6_branch_creation", screenshotConfig);
    }

    // Submit form
    cy.get(".justify-center > .rounded-md").click();
  });

  it("should update the device and an interface", function () {
    // Access the devices
    cy.get("[href^='/objects/Device'] > .group", { timeout: 10000 }).click();

    // Access the device
    cy.contains(DEVICE).click();

    // Access the interfaces
    cy.get(".-mb-px > .border-transparent").click();

    // Access the interface
    const regex = new RegExp(`^${INTERFACE}$`); // Regex for exact match
    cy.contains(regex).click();

    // Open the edit button
    cy.get(".md\\:pl-64 > .flex-col > .bg-custom-white > :nth-child(2) > .rounded-md").click();

    // Update the description
    cy.get(":nth-child(2) > .relative > .block").clear();
    cy.get(":nth-child(2) > .relative > .block").type(NEW_INTERFACE_DESCRIPTION);
    cy.get(":nth-child(2) > .relative > .block").blur();

    if (this.screenshots) {
      cy.screenshot("tutorial_6_interface_update", screenshotConfig);
    }

    // Submit
    cy.contains("Save").click();
  });
});
