/// <reference types="cypress" />

import { NEW_ADMIN_ACCOUNT_LABEL } from "../../mocks/e2e/accounts";
import { ADMIN_CREDENTIALS, SCREENSHOT_ENV_VARIABLE, screenshotConfig } from "../../utils";

describe("Tutorial - Part 2", () => {
  beforeEach(function () {
    cy.login(ADMIN_CREDENTIALS.username, ADMIN_CREDENTIALS.password);

    this.screenshots = Cypress.env(SCREENSHOT_ENV_VARIABLE);
  });

  it("should check the historical data", function () {
    cy.visit("/");

    // Access the accounts list
    cy.get("[href='/objects/Account'] > .group").click();

    // Access admin account
    cy.contains(NEW_ADMIN_ACCOUNT_LABEL).should("exist");
    cy.contains(NEW_ADMIN_ACCOUNT_LABEL).click();

    // Toggle the data-only field
    cy.get(".sm\\:p-0").within(() => {
      // The label should be the new one
      cy.contains("Label").siblings(".flex").should("have.text", NEW_ADMIN_ACCOUNT_LABEL);
    });

    cy.get(".react-datepicker__input-container > .relative > .block").click();

    if (this.screenshots) {
      cy.screenshot("tutorial_2_historical", screenshotConfig);
    }

    // TODO: Define a previous date and verify if the label is correctly the old one
    // cy.screenshot("tutorial_2_historical_set", screenshotConfig);
  });
});
