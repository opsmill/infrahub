/// <reference types="cypress" />

import { PROPOSED_CHANGES_BRANCH, PROPOSED_CHANGES_NAME } from "../mocks/e2e/proposed-changes";
import { ADMIN_CREDENTIALS, SCREENSHOT_ENV_VARIABLE, screenshotConfig } from "../utils";

describe("Main application", () => {
  beforeEach(function () {
    cy.login(ADMIN_CREDENTIALS.username, ADMIN_CREDENTIALS.password);

    cy.visit("/");

    this.screenshots = Cypress.env(SCREENSHOT_ENV_VARIABLE);
  });

  it("should create a Proposed Changes", function () {
    // Access the proposed changes view
    cy.contains("Proposed changes").click();

    // Open the creat panel
    cy.get(".bg-white > .p-2").click();

    // Type the PC name
    cy.get(".grid > :nth-child(1) > .relative > .block").type(PROPOSED_CHANGES_NAME);

    // Open the branch selector
    cy.get(".space-y-12 > :nth-child(1) > .grid > :nth-child(2)").within(() => {
      cy.get("[id^=headlessui-combobox-button-]").click();
      cy.contains(PROPOSED_CHANGES_BRANCH).click();
    });

    if (this.screenshots) {
      cy.screenshot("proposed-changes-1-create", screenshotConfig);
    }

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
    cy.contains(PROPOSED_CHANGES_NAME).should("exist");
  });

  it("should access the Proposed Changes details", function () {
    // Access the proposed changes view
    cy.contains("Proposed changes").click();

    // Access the new PC details
    cy.get(".grid").within(() => {
      cy.contains(PROPOSED_CHANGES_NAME).click();
    });

    // Loader should not exist
    cy.contains("Just a moment").should("not.exist");

    if (this.screenshots) {
      cy.screenshot("proposed-changes-2-details", screenshotConfig);
    }

    // Check if the details are correct
    cy.get(".flex-3").within(() => {
      cy.contains(PROPOSED_CHANGES_NAME).should("exist");
    });
  });

  it("should access the Proposed Changes diff view", function () {
    // Access the proposed changes view
    cy.contains("Proposed changes").click();

    // Access the new PC details
    cy.contains(PROPOSED_CHANGES_NAME).click();

    // Loader should not exist
    cy.contains("Just a moment").should("not.exist");

    if (this.screenshots) {
      cy.screenshot("proposed-changes-2-details", screenshotConfig);
    }

    // Check if the details are correct
    cy.get(".-mb-px").within(() => {
      cy.contains("Data").click();
    });

    // Check if there are some items in the data diff view
    cy.get("div.text-xs").find("div").should("have.length.above", 1);

    cy.contains("203.0.113.242/29").click();

    cy.contains("address").click();

    if (this.screenshots) {
      cy.screenshot("proposed-changes-3-data-diff", screenshotConfig);
    }

    cy.get(
      ":nth-child(4) > :nth-child(1) > :nth-child(1) > :nth-child(2) > :nth-child(1) > :nth-child(1) > .rounded-md > :nth-child(1)"
    ).within(() => {
      cy.contains("IS_PROTECTED").should("exist");
    });
  });
});
