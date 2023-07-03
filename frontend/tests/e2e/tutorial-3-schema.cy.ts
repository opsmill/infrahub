/// <reference types="cypress" />

import { SCREENSHOT_ENV_VARIABLE, screenshotConfig } from "../utils";

describe("Tutorial - Part 3", () => {
  beforeEach(function () {
    cy.visit("/");
    this.screenshots = Cypress.env(SCREENSHOT_ENV_VARIABLE);
  });

  it("should access the schema list", function () {
    // Click on the schema link
    cy.get("[href='/schema'] > .group").click();

    if (this.screenshots) {
      cy.screenshot("tutorial_3_schema", screenshotConfig);
    }
  });
});
