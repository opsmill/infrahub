/// <reference types="cypress" />

import {
  PROPOSED_CHANGES_BRANCH_CONFLICT,
  PROPOSED_CHANGES_NAME,
} from "../mocks/e2e/proposed-changes";
import { ADMIN_CREDENTIALS, SCREENSHOT_ENV_VARIABLE, screenshotConfig } from "../utils";

describe("Main application", () => {
  beforeEach(function () {
    cy.login(ADMIN_CREDENTIALS.username, ADMIN_CREDENTIALS.password);

    cy.visit("/");

    this.screenshots = Cypress.env(SCREENSHOT_ENV_VARIABLE);
  });

  it("should create a Proposed Changes with conflicts", function () {
    // Access the proposed changes view
    cy.contains("Proposed changes").click();

    // Open the creat panel
    cy.get(".bg-white > .p-2").click();

    // Type the PC name
    cy.get(".grid > :nth-child(1) > .relative > .block").type(PROPOSED_CHANGES_NAME);

    // Open the branch selector
    cy.get(".space-y-12 > :nth-child(1) > .grid > :nth-child(2)").within(() => {
      cy.get("[id^=headlessui-combobox-button-]").click();
      cy.contains(PROPOSED_CHANGES_BRANCH_CONFLICT).click();
    });

    // Will intercept the mutation request
    cy.intercept("/graphql/main").as("ProposedChangesCreate");

    // Submit the form
    cy.get(".justify-end").within(() => {
      cy.contains("Create").click();
    });

    // Wait for the mutation to succeed
    cy.wait("@ProposedChangesCreate");

    cy.contains("Create ProposedChange").should("not.exist");

    // The new PC should exist
    cy.get(".flex-1 > div > .grid").within(() => {
      cy.contains(PROPOSED_CHANGES_NAME).should("exist");
    });
  });

  it("should access the Proposed Changes checks view", function () {
    // Access the proposed changes view
    cy.contains("Proposed changes").click();

    // Access the new PC details
    cy.get(".grid").within(() => {
      cy.contains(PROPOSED_CHANGES_NAME).click();
    });

    cy.get(".-mb-px").within(() => {
      cy.contains("Checks").click();
    });

    cy.get(".grid > :nth-child(2)").within(() => {
      cy.contains("DataValidator", { timeout: 30000 }).should("exist");
      cy.contains("0/1", { timeout: 30000 }).should("exist");
    });

    cy.get(".flex-col > .justify-between.items-center").within(() => {
      cy.contains("19").should("exist");
    });

    if (this.screenshots) {
      cy.screenshot("validators-1-list", screenshotConfig);
    }
  });
});
