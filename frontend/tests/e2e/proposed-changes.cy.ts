/// <reference types="cypress" />

import {
  PROPOSED_CHANGES_BRANCH,
  PROPOSED_CHANGES_NAME,
  PROPOSED_CHANGE_COMMENT_1,
  PROPOSED_CHANGE_COMMENT_2,
  PROPOSED_CHANGE_COMMENT_3,
} from "../mocks/e2e/proposed-changes";
import { ADMIN_CREDENTIALS, SCREENSHOT_ENV_VARIABLE, screenshotConfig } from "../utils";

describe("Main application", () => {
  beforeEach(function () {
    cy.login(ADMIN_CREDENTIALS.username, ADMIN_CREDENTIALS.password);

    cy.visit("/");

    this.screenshots = Cypress.env(SCREENSHOT_ENV_VARIABLE);
  });

  it("should create a Proposed Changes", function () {
    // Access the proposed changes view
    cy.contains("Proposed Changes").click();

    // Open the creat panel
    cy.get("[data-cy='add-proposed-changes-button']").click();

    // Type the PC name
    cy.get("#Name").type(PROPOSED_CHANGES_NAME);

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
    cy.contains("button", "Create").click();

    // Wait for the mutation to succeed
    cy.wait("@ProposedChangesCreate");

    cy.contains("Create ProposedChange").should("not.exist");

    // The new PC should exist
    cy.contains(PROPOSED_CHANGES_NAME).should("exist");

    // We should see the comment section
    cy.contains("Add your comment here...").should("exist");
  });

  it("should access the Proposed Changes details", function () {
    // Access the proposed changes view
    cy.contains("Proposed Changes").click();

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

  it("should access the Proposed Changes details and update the comments", function () {
    // Access the proposed changes view
    cy.contains("Proposed Changes").click();

    // Access the new PC details
    cy.get(".grid").within(() => {
      cy.contains(PROPOSED_CHANGES_NAME).click();
    });

    // Loader should not exist
    cy.contains("Just a moment").should("not.exist");

    // Type the first comment in the add comment section
    cy.get("[data-cy='codemirror-editor']").first().type(PROPOSED_CHANGE_COMMENT_1);

    cy.intercept("/graphql/main").as("CreateComment1");

    // Send request
    cy.contains("button", "Comment").click();

    cy.wait("@CreateComment1");

    // Check if the thread has been created
    cy.get("[data-cy='thread']")
      .first()
      .within(() => {
        // The "created by" should be correct
        cy.contains("Admin").should("exist");

        // The comment should be displayed
        cy.contains(PROPOSED_CHANGE_COMMENT_1).should("exist");

        // Add reply
        cy.contains("button", "Reply").click();

        cy.get("[data-cy='codemirror-editor']").first().type(PROPOSED_CHANGE_COMMENT_2);

        cy.intercept("/graphql/main").as("CreateComment2");

        // Send request
        cy.contains("button", "Comment").click();

        cy.wait("@CreateComment2");

        // Comment should exist
        cy.contains(PROPOSED_CHANGE_COMMENT_2).should("exist");

        if (this.screenshots) {
          cy.screenshot("proposed-changes-3-comments", screenshotConfig);
        }

        // Add third comment
        cy.contains("button", "Reply").click();
        cy.get("[data-cy='codemirror-editor']").first().type(PROPOSED_CHANGE_COMMENT_3);

        // Mark as resolved once commented
        cy.contains("Resolve thread").click();
      });

    cy.intercept("/graphql/main").as("CreateComment3");

    cy.get("[data-cy='modal-confirm-buttons']").within(() => {
      // Send request
      cy.contains("Confirm").click();
    });

    // Send request
    cy.contains("button", "Comment").first().click();

    cy.wait("@CreateComment3");

    // Add third comment
    cy.contains(PROPOSED_CHANGE_COMMENT_3).should("exist");

    cy.contains("Resolved").should("not.have.class", "cursor-pointer");
    cy.get("[data-cy='checkbox']").should("be.disabled");

    if (this.screenshots) {
      cy.screenshot("proposed-changes-5-comments-resolved", screenshotConfig);
    }
  });

  it("should access the Proposed Changes diff view", function () {
    // Access the proposed changes view
    cy.contains("Proposed Changes").click();

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
      cy.screenshot("proposed-changes-6-data-diff", screenshotConfig);
    }

    cy.contains("IS_PROTECTED").should("exist");
  });
});
