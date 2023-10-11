/// <reference types="cypress" />

import {
  MAIN_BRANCH_NAME,
  NEW_BRANCH_NAME,
  NEW_ORGANIZATION_DESCRIPTION,
  ORGANIZATION_DESCRIPTION,
  ORGANIZATION_NAME,
} from "../../mocks/e2e/organizations";
import { ADMIN_CREDENTIALS, SCREENSHOT_ENV_VARIABLE, screenshotConfig } from "../../utils";

describe("Tutorial - Part 1", () => {
  beforeEach(function () {
    cy.login(ADMIN_CREDENTIALS.username, ADMIN_CREDENTIALS.password);

    cy.visit("/");

    this.screenshots = Cypress.env(SCREENSHOT_ENV_VARIABLE);
  });

  it("should create a new organization", function () {
    cy.visit("/");

    // Select the Admin object in the menu
    cy.get("[href='/objects/CoreOrganization'] > .group").click();

    // Click on the + icon
    cy.get("[data-cy='create']").click();

    // Add organization name
    cy.get(".grid > :nth-child(1) > .relative > .block").type(ORGANIZATION_NAME);
    cy.get(".grid > :nth-child(3) > .relative > .block").type(ORGANIZATION_DESCRIPTION);

    if (this.screenshots) {
      cy.screenshot("tutorial_1_organization_create", screenshotConfig);
    }

    cy.intercept("POST", "/graphql/main").as("Request");

    cy.get(".flex-col > .justify-end").within(() => {
      cy.contains("Create").click();

      cy.wait("@Request");
    });
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

  it("should update the organization", function () {
    cy.visit(`/?branch=${NEW_BRANCH_NAME}`);

    // Select the Admin object in the menu
    cy.get(`[href='/objects/CoreOrganization?branch=${NEW_BRANCH_NAME}'] > .group`).click();

    // Select the organization
    cy.contains(ORGANIZATION_NAME).should("exist");

    if (this.screenshots) {
      cy.screenshot("tutorial_1_organizations", screenshotConfig);
    }

    cy.contains(ORGANIZATION_NAME).click();

    cy.get(".bg-gray-500").should("not.exist");

    cy.get(".sm\\:divide-y > :nth-child(2) > div.flex > .mt-1").should(
      "have.text",
      ORGANIZATION_NAME
    );

    if (this.screenshots) {
      cy.screenshot("tutorial_1_organization_details", screenshotConfig);
    }

    // Open the edit panel
    cy.contains("Edit").click();

    // Verify that the field is pre-populated
    cy.get(".grid > :nth-child(1) > .relative > .block").should("have.value", ORGANIZATION_NAME);

    // Update the label
    cy.get(":nth-child(3) > .relative > .block").should("have.value", ORGANIZATION_DESCRIPTION);
    cy.get(":nth-child(3) > .relative > .block").clear();
    cy.get(":nth-child(3) > .relative > .block").type(NEW_ORGANIZATION_DESCRIPTION);

    if (this.screenshots) {
      cy.screenshot("tutorial_1_organization_edit", screenshotConfig);
    }

    // Will intercept the mutation request
    cy.intercept(`/graphql/${NEW_BRANCH_NAME}`).as("Request");

    // Submit the form
    cy.contains("Save").click();

    // Wait for the mutation to succeed
    cy.wait("@Request");

    // The new label should be saved
    cy.get(".sm\\:p-0 > :nth-child(1) > :nth-child(4)").within(() => {
      cy.contains(NEW_ORGANIZATION_DESCRIPTION).should("exist");
    });
  });

  it("should access the organzation diff", function () {
    // List the branches
    cy.get("[href='/branches'] > .group").click();

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
    cy.contains(ORGANIZATION_NAME, { matchCase: false }).click();

    if (this.screenshots) {
      cy.screenshot("tutorial_1_branch_diff", screenshotConfig);
    }

    // The old + new label should be displayed
    cy.get(".text-xs > .shadow").within(() => {
      cy.contains(ORGANIZATION_NAME, { matchCase: false }).should("exist");
      cy.contains(NEW_ORGANIZATION_DESCRIPTION).should("exist");
    });

    // Go back to details
    cy.get(".isolate > .bg-gray-100").click();

    // Merge the branch
    cy.get(".bg-green-500").click();

    cy.contains("Branch merged successfully!").should("exist");
  });
});
