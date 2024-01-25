/// <reference types="cypress" />

import { ADMIN_CREDENTIALS, SCREENSHOT_ENV_VARIABLE, screenshotConfig } from "../../constants";

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
    cy.get("[data-cy='create-branch-button']").click();

    // Add the new branch name
    cy.get("[id='New branch name']").type(NEW_BRANCH);

    // Turn off data-only field
    cy.contains("Data only").click();

    if (this.screenshots) {
      cy.screenshot("tutorial_6_branch_creation", screenshotConfig);
    }

    // Submit form
    cy.contains("Create").click();
  });

  it("should update the device and an interface", function () {
    // Access the devices
    cy.get("[href^='/objects/InfraDevice'] > .group", { timeout: 10000 }).click();

    // Access the device
    cy.contains(DEVICE).click();

    // Access the interfaces
    cy.contains("Interfaces").click();

    // Access the interface
    const regex = new RegExp(`^${INTERFACE}$`); // Regex for exact match
    cy.contains(regex).click();

    // Open the edit button
    cy.contains("Edit").click();

    // Update the description
    cy.get(":nth-child(2) > .relative > .block").clear();
    cy.get(":nth-child(2) > .relative > .block").type(NEW_INTERFACE_DESCRIPTION, {
      delay: 0,
      force: true,
    });
    cy.get(":nth-child(2) > .relative > .block").blur();

    if (this.screenshots) {
      cy.screenshot("tutorial_6_interface_update", screenshotConfig);
    }

    // Submit
    cy.contains("Save").click();
  });
});
