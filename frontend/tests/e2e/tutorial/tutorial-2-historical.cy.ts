/// <reference types="cypress" />

import { ADMIN_CREDENTIALS, SCREENSHOT_ENV_VARIABLE, screenshotConfig } from "../../constants";
import { ORGANIZATION_NAME } from "../../mocks/e2e/organizations";

describe("Tutorial - Part 2", () => {
  beforeEach(function () {
    cy.login(ADMIN_CREDENTIALS.username, ADMIN_CREDENTIALS.password);

    this.screenshots = Cypress.env(SCREENSHOT_ENV_VARIABLE);
  });

  it("should check the historical data", function () {
    cy.visit("/");

    // Access the accounts list
    cy.get("[href='/objects/CoreOrganization'] > .group").click();

    // Access admin account
    cy.contains(ORGANIZATION_NAME).click();

    // Toggle the data-only field
    cy.get(".sm\\:p-0").within(() => {
      // The label should be the new one
      cy.contains("Name").siblings(".flex").should("have.text", ORGANIZATION_NAME);
    });

    cy.get(".react-datepicker__input-container > .relative > .block").click();

    if (this.screenshots) {
      cy.screenshot("tutorial_2_historical", screenshotConfig);
    }

    // TODO: Define a previous date and verify if the label is correctly the old one
    // cy.screenshot("tutorial_2_historical_set", screenshotConfig);
  });
});
