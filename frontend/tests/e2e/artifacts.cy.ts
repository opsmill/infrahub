/// <reference types="cypress" />

import { ADMIN_CREDENTIALS, SCREENSHOT_ENV_VARIABLE, screenshotConfig } from "../constants";
import { ARTIFACT_DEFINITION_FULL_NAME, ARTIFACT_DEFINITION_NAME } from "../mocks/e2e/artifacts";

describe("Main application", () => {
  beforeEach(function () {
    cy.login(ADMIN_CREDENTIALS.username, ADMIN_CREDENTIALS.password);

    cy.visit("/");

    this.screenshots = Cypress.env(SCREENSHOT_ENV_VARIABLE);
  });

  it("should access the artifacts definition list and generate an artifact", function () {
    // Access the proposed changes view
    cy.contains("Artifact Definition").click();

    // Wait after the artifacts defintions to be ready
    // (may require a few attempts while the repo is loaded)
    cy.contains(ARTIFACT_DEFINITION_NAME, { timeout: 30000 }).should("exist");

    // Access the artifact definition
    cy.contains(ARTIFACT_DEFINITION_NAME).click();

    // Loader should not exist
    cy.contains("Just a moment").should("not.exist");

    if (this.screenshots) {
      cy.screenshot("artifacts-1-definition-details", screenshotConfig);
    }

    // Will intercept the API request
    cy.intercept("/api/artifact/generate/*").as("ArtifactsCreation");

    // Generate the artifacts
    cy.contains("button", "Generate").click();

    // Wait for the mutation to succeed
    cy.wait("@ArtifactsCreation");
  });

  it("should access the artifacts list", function () {
    // Access the proposed changes view
    cy.contains("Artifact").click();

    // There should be more than 1 artifacts
    cy.get("tbody.bg-custom-white").find("tr").should("have.length.above", 1);

    // Click to access artifact details
    cy.contains(ARTIFACT_DEFINITION_FULL_NAME).first().click();

    // Loader should not exist
    cy.contains("Just a moment").should("not.exist");

    if (this.screenshots) {
      cy.screenshot("artifacts-2-artifact-details", screenshotConfig);
    }

    cy.get(".p-4 > .relative > .shadow-sm > .npm__react-simple-code-editor__textarea").should(
      "include.value",
      "no aaa root"
    );
  });
});
