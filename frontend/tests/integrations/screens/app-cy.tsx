/// <reference types="cypress" />

import React from "react";
import App from "../../../src/App";

describe("Branches screen", () => {
  const branchName = "test-branch-6";

  const branchDescription = "Branch description here";

  it("should render the app and create a branch", () => {
    cy.viewport(1920, 1080);

    cy.mount(<App />);

    // Intercept and wait config query
    cy.intercept("GET", "/config", []).as("getConfig");

    cy.wait("@getConfig");

    // Intercept and wait schema query
    cy.intercept("GET", "/schema", []).as("getSchema");

    cy.wait("@getSchema");

    // Click on the create branch button
    cy.get("#headlessui-popover-button-\\:rk\\:").click();

    // Check if the popover is rendered
    cy.get("#headlessui-popover-panel-\\:rp\\:").should("exist");

    // Type in the field for branch name
    cy.get(":nth-child(2) > .flex-col > :nth-child(1)").type(branchName, { delay: 0, force: true });

    // Type in the field for branch description
    cy.get(":nth-child(2) > .flex-col > :nth-child(2)").type(branchDescription, {
      delay: 0,
      force: true,
    });

    // Click on the submit button
    cy.get(".justify-center > .py-1\\.5").click();

    // Check if the content of the selector is the new branch
    cy.get(".ml-2\\.5").should("contain", branchName);
  });
});
