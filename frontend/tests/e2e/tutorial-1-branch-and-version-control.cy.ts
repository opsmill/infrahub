/// <reference types="cypress" />

const MAIN_BRANCH_NAME = "main";
const NEW_BRANCH_NAME = "cr1234";
const ADMIN_ACCOUNT_NAME = "admin";
const ADMIN_ACCOUNT_LABEL = "Admin";
const NEW_ADMIN_ACCOUNT_LABEL = "Administrator";

describe("Tutorial - Part 1", () => {
  beforeEach(() => {
    cy.viewport(1920, 1080);

    cy.visit("/");
  });

  it("should create a new branch", () => {
    // The branch selector should contain the main branch name
    cy.get(":nth-child(1) > :nth-child(1) > .border").should("have.text", MAIN_BRANCH_NAME);

    // Click to open the branch creation form
    cy.get("#headlessui-popover-button-\\:r9\\: > .py-1\\.5").click();

    // Fill the new branch name
    cy.get(".flex-col > :nth-child(1) > .block").type(NEW_BRANCH_NAME);

    // Submit the form
    // cy.get('.justify-center > .rounded-md').click(); // TODO: Uncomment for CI

    // Verify if the new branch is selected
    // cy.get(":nth-child(1) > :nth-child(1) > .border").should("have.text", NEW_BRANCH); // TODO: Uncomment for CI
  });

  it("should update the Admin Account", () => {
    // Select the Admin object in the menu
    cy.get("[href='/objects/account'] > .group").click();

    // Select the admin account
    cy.get(".bg-white > :nth-child(5) > :nth-child(1)").should("have.text", ADMIN_ACCOUNT_NAME);
    cy.get(".bg-white > :nth-child(5) > :nth-child(1)").click();
    cy.get(".sm\\:divide-y > :nth-child(2) > div.flex > .mt-1").should(
      "have.text",
      ADMIN_ACCOUNT_NAME
    );

    // Open the edit panel
    cy.get(".md\\:pl-64 > .flex-col > .bg-white > :nth-child(2) > .rounded-md").click();

    // Verify that the field is pre-populated
    cy.get(".grid > :nth-child(1) > .relative > .block").should("have.value", ADMIN_ACCOUNT_NAME);

    // Update the label
    // cy.get(":nth-child(3) > .relative > .block").should("have.value", ADMIN_ACCOUNT_LABEL); // TODO: Uncomment for CI
    cy.get(":nth-child(3) > .relative > .block").clear();
    cy.get(":nth-child(3) > .relative > .block").type(NEW_ADMIN_ACCOUNT_LABEL);

    // Submit the form
    cy.get(".mt-6 > .bg-blue-500").click();

    // The new label should be saved
    cy.get(":nth-child(3) > .relative > .block").should("have.value", NEW_ADMIN_ACCOUNT_LABEL);
  });

  it("should access the Admin Account diff", () => {
    // List the branches
    cy.get("#headlessui-disclosure-panel-\\:r5\\: > a > .group").click();

    // Find and click on the new branch
    cy.contains(NEW_BRANCH_NAME).click();

    // The branch details should be ok
    cy.get(".divide-y > :nth-child(1) > .flex").should("have.text", NEW_BRANCH_NAME);

    // Access to the branch diff
    cy.get(".isolate > .bg-gray-100").click();

    // Open the tab to check the diff
    cy.contains(NEW_ADMIN_ACCOUNT_LABEL).click();

    // The old + new label should be displayed
    cy.get(
      ":nth-child(1) > :nth-child(1) > .flex-1 > .pr-0 > :nth-child(2) > .font-semibold > .items-center > :nth-child(1) > .group > .flex"
    ).should("have.text", ADMIN_ACCOUNT_LABEL);
    cy.get(
      ":nth-child(1) > :nth-child(1) > .flex-1 > .pr-0 > :nth-child(2) > .font-semibold > .items-center > :nth-child(3) > .group > .flex"
    ).should("have.text", NEW_ADMIN_ACCOUNT_LABEL);

    // Go back to details
    cy.get(".isolate > .bg-gray-100").click();

    // Merge the branch
    // cy.get('.bg-green-600').click(); // TODO: Uncomment for CI
  });
});
