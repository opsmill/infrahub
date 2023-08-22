/// <reference types="cypress" />

import {
  ADMIN_ACCOUNT_LABEL,
  ADMIN_ACCOUNT_NAME,
  MAIN_BRANCH_NAME,
  NEW_ADMIN_ACCOUNT_LABEL,
  NEW_BRANCH_NAME,
} from "../../mocks/e2e/accounts";
import { ADMIN_CREDENTIALS, SCREENSHOT_ENV_VARIABLE, screenshotConfig } from "../../utils";

describe("Tutorial - Part 1", () => {
  beforeEach(function () {
    cy.login(ADMIN_CREDENTIALS.username, ADMIN_CREDENTIALS.password);

    cy.visit("/");

    this.screenshots = Cypress.env(SCREENSHOT_ENV_VARIABLE);
  });

  it("should create a new branch", function () {
    // The branch selector should contain the main branch name
    cy.get(":nth-child(1) > :nth-child(1) > .border").should("have.text", MAIN_BRANCH_NAME);

    // Click to open the branch creation form
    cy.get("#headlessui-popover-button-\\:r8\\: > .py-1\\.5").click();

    // Fill the new branch name
    cy.get(".flex-col > :nth-child(1) > .block").type(NEW_BRANCH_NAME);

    if (this.screenshots) {
      cy.screenshot("tutorial_1_branch_creation", screenshotConfig);
    }

    // Submit the form
    cy.get(".justify-center > .rounded-md").click();

    // Verify if the new branch is selected
    cy.get(":nth-child(1) > :nth-child(1) > .border").should("have.text", NEW_BRANCH_NAME);
  });

  it("should update the Admin Account", function () {
    cy.visit(`/?branch=${NEW_BRANCH_NAME}`);

    // Select the Admin object in the menu
    cy.get(`[href='/objects/Account?branch=${NEW_BRANCH_NAME}'] > .group`).click();

    // Loader should not exist
    cy.contains("Just a moment").should("not.exist");

    // Select the admin account
    cy.contains(ADMIN_ACCOUNT_NAME).should("exist");

    if (this.screenshots) {
      cy.screenshot("tutorial_1_accounts", screenshotConfig);
    }

    cy.contains(ADMIN_ACCOUNT_NAME).click();

    // Loader should not exist
    cy.contains("Just a moment").should("not.exist");

    cy.get(".sm\\:divide-y > :nth-child(2) > div.flex > .mt-1").should(
      "have.text",
      ADMIN_ACCOUNT_NAME
    );

    if (this.screenshots) {
      cy.screenshot("tutorial_1_account_details", screenshotConfig);
    }

    // Open the edit panel
    cy.get(".md\\:pl-64 > :nth-child(2) > .flex-col > .bg-custom-white").within(() => {
      cy.contains("Edit").click();
    });

    // Verify that the field is pre-populated
    cy.get(".grid > :nth-child(1) > .relative > .block").should("have.value", ADMIN_ACCOUNT_NAME);

    // Update the label
    cy.get(":nth-child(3) > .relative > .block").should("have.value", ADMIN_ACCOUNT_LABEL);
    cy.get(":nth-child(3) > .relative > .block").clear();
    cy.get(":nth-child(3) > .relative > .block").type(NEW_ADMIN_ACCOUNT_LABEL);

    // Loader should not exist
    cy.contains("Just a moment").should("not.exist");

    if (this.screenshots) {
      cy.screenshot("tutorial_1_account_edit", screenshotConfig);
    }

    // Submit the form
    cy.contains("Save").click();

    // The new label should be saved
    cy.get(":nth-child(3) > .relative > .block").should("have.value", NEW_ADMIN_ACCOUNT_LABEL);
  });

  it("should access the Admin Account diff", function () {
    // List the branches
    cy.get("[href='/branches'] > .group").click();

    cy.contains("Just a moment").should("not.exist");

    if (this.screenshots) {
      cy.screenshot("tutorial_1_branch_list", screenshotConfig);
    }

    // Find and click on the new branch
    cy.contains(NEW_BRANCH_NAME).click();

    if (this.screenshots) {
      cy.screenshot("tutorial_1_branch_details", screenshotConfig);
    }

    // The branch details should be ok
    cy.get(".divide-y > :nth-child(1) > .flex").should("have.text", NEW_BRANCH_NAME);

    // Access to the branch diff
    cy.contains("Diff").click();

    // Open the tab to check the diff
    cy.contains(NEW_ADMIN_ACCOUNT_LABEL).click();

    if (this.screenshots) {
      cy.screenshot("tutorial_1_branch_diff", screenshotConfig);
    }

    // The old + new label should be displayed
    cy.get(":nth-child(1) > .group\\/tooltip > .flex").should("have.text", ADMIN_ACCOUNT_LABEL);

    cy.get(":nth-child(3) > .group\\/tooltip > .flex").should("have.text", NEW_ADMIN_ACCOUNT_LABEL);

    // Go back to details
    cy.get(".isolate > .bg-gray-100").click();

    // Merge the branch
    cy.get(".bg-green-500").click();

    cy.contains("Branch merged successfully!").should("exist");
  });
});
