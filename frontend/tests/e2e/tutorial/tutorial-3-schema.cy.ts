/// <reference types="cypress" />

import { ADMIN_CREDENTIALS, SCREENSHOT_ENV_VARIABLE, screenshotConfig } from "../../utils";

describe("Tutorial - Part 3", () => {
  beforeEach(function () {
    cy.login(ADMIN_CREDENTIALS.username, ADMIN_CREDENTIALS.password);

    cy.visit("/");

    this.screenshots = Cypress.env(SCREENSHOT_ENV_VARIABLE);
  });

  it("should access the schema list", function () {
    // Click on the schema link
    cy.get("[href='/schema'] > .group").click();

    cy.contains("Account").should("exist");

    if (this.screenshots) {
      cy.screenshot("tutorial_3_schema", screenshotConfig);
    }
  });
});
