/// <reference types="cypress" />

import { ADMIN_CREDENTIALS, SCREENSHOT_ENV_VARIABLE, screenshotConfig } from "../../constants";
import {
  MAIN_BRANCH_NAME,
  NEW_BRANCH_NAME,
  NEW_ORGANIZATION_DESCRIPTION,
  ORGANIZATION_DESCRIPTION,
  ORGANIZATION_NAME,
} from "../../mocks/e2e/organizations";

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
    cy.contains("Create Organization").should("be.visible"); // Assert that the form is ready
    cy.get("#Name").clear({ force: true }); // Workaround to prevent cypress bug "cy.type() failed because it targeted a disabled element."

    cy.get("#Name").type(ORGANIZATION_NAME);
    cy.get("#Description").type(ORGANIZATION_DESCRIPTION);

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
    cy.get("[data-cy='branch-select-menu']").should("have.text", MAIN_BRANCH_NAME);

    // Click to open the branch creation form
    cy.get("[data-cy='create-branch-button']").click();

    // Fill the new branch name
    cy.contains("Create a new branch").should("be.visible"); // Assert that the form is ready
    cy.get("[id='New branch name']").type(NEW_BRANCH_NAME);

    if (this.screenshots) {
      cy.screenshot("tutorial_1_branch_creation", screenshotConfig);
    }

    // Submit the form
    cy.contains("button", "Create branch").click();

    // Verify if the new branch is selected
    cy.get("[data-cy='branch-select-menu']").contains(NEW_BRANCH_NAME);
  });

  it("should update the organization", function () {
    cy.visit(`/?branch=${NEW_BRANCH_NAME}`);

    // Select the CoreOrganization object in the menu
    cy.get("[data-cy='sidebar-menu']").within(() => {
      cy.contains("Organization").click();
    });

    // Select the organization
    cy.contains(ORGANIZATION_NAME).should("exist");

    if (this.screenshots) {
      cy.screenshot("tutorial_1_organizations", screenshotConfig);
    }

    cy.contains(ORGANIZATION_NAME).click();

    cy.get("[data-cy='side-panel-background']").should("not.exist");

    cy.contains("Name" + ORGANIZATION_NAME);
    cy.contains("Description" + ORGANIZATION_DESCRIPTION);

    if (this.screenshots) {
      cy.screenshot("tutorial_1_organization_details", screenshotConfig);
    }

    // Open the edit panel
    cy.contains("button", "Edit").click();

    // Verify that the field is pre-populated
    cy.contains("Name *must be unique").should("be.visible"); // Assert that the form is ready
    cy.get("#Name").should("have.value", ORGANIZATION_NAME);
    cy.get("#Description").should("have.value", ORGANIZATION_DESCRIPTION);

    // Update the label
    cy.get("#Description").clear();
    cy.get("#Description").type(NEW_ORGANIZATION_DESCRIPTION);

    if (this.screenshots) {
      cy.screenshot("tutorial_1_organization_edit", screenshotConfig);
    }

    // Will intercept the mutation request
    cy.intercept(`/graphql/${NEW_BRANCH_NAME}`).as("Request");

    // Submit the form
    cy.contains("button", "Save").click();

    // Wait for the mutation to succeed
    cy.wait("@Request");

    // The new description should be saved
    cy.contains("Name" + ORGANIZATION_NAME);
    cy.contains("Description" + NEW_ORGANIZATION_DESCRIPTION);
  });

  it("should access the organization diff", function () {
    // List the branches
    cy.get("[data-cy='sidebar-menu']").contains("Branches").click();

    if (this.screenshots) {
      cy.screenshot("tutorial_1_branch_list", screenshotConfig);
    }

    // Find and click on the new branch
    cy.get("[data-cy='branches-items']").contains(NEW_BRANCH_NAME).click();

    if (this.screenshots) {
      cy.screenshot("tutorial_1_branch_details", screenshotConfig);
    }

    // The branch details should be ok
    cy.contains("Name" + NEW_BRANCH_NAME);

    // Access to the branch diff
    cy.contains("Diff").click();

    // Open the tab to check the diff
    cy.contains(ORGANIZATION_NAME, { matchCase: false }).click();

    if (this.screenshots) {
      cy.screenshot("tutorial_1_branch_diff", screenshotConfig);
    }

    // The old + new label should be displayed
    cy.get("[data-cy='data-diff']").within(() => {
      cy.contains(ORGANIZATION_NAME, { matchCase: false }).should("exist");
      cy.contains(NEW_ORGANIZATION_DESCRIPTION).should("exist");
    });

    // Go back to details
    cy.contains("button", "Details").click();

    // Merge the branch
    cy.contains("button", "Merge").click();

    cy.contains("Branch merged successfully!").should("be.visible");
  });
});
