/// <reference types="cypress" />

import { ADMIN_CREDENTIALS } from "../constants";

const ETHERNET_NAME = "Ethernet11";

const ACCOUNT = "Account";

const ACCOUNT_NAME = "Operation Team";

describe("Object update", () => {
  beforeEach(function () {
    cy.login(ADMIN_CREDENTIALS.username, ADMIN_CREDENTIALS.password);

    cy.visit("/");
  });

  it("should access the object's metadata", function () {
    // Access the interfaces view
    cy.get("[data-cy='sidebar-menu']").within(() => {
      cy.contains("Interface L2").click();
    });

    // Access an interface
    cy.contains(ETHERNET_NAME).first().click();

    // Open the metadata panel
    cy.get(".sm\\:p-0").within(() => {
      cy.contains("Status")
        .parent()
        .within(() => {
          cy.get("[data-cy='metadata-button']").click();

          // Check the source
          cy.contains(ACCOUNT_NAME).should("exist");

          // Edit the metadata
          cy.get("[data-cy='metadata-edit-button']").click();
        });
    });

    // Is visible
    cy.get("#is\\ visible").should("be.checked");

    // Is protected
    cy.get("#is\\ protected").should("not.be.checked");

    // Owner select
    cy.get(".grid-cols-1 > :nth-child(1) > .grid").within(() => {
      // The first select should exists
      cy.get("[id^=headlessui-combobox-input-]").first();

      // Open the select
      cy.get("[id^=headlessui-combobox-button-]").click();

      // Check if the options have a length of 4
      cy.get("[id^=headlessui-combobox-options-]").find("li").should("have.length", 4);

      // Choose the account
      cy.contains(ACCOUNT).click();

      // Second select should exist
      cy.get("[id^=headlessui-combobox-input-]").first().should("have.value", ACCOUNT);

      // Second select should exist
      cy.get("[id^=headlessui-combobox-input-]").eq(1);

      // Open the select
      cy.get("[id^=headlessui-combobox-button-]").eq(1).click();

      // Choose the account
      cy.contains(ACCOUNT_NAME).click();

      // Second select should exist
      cy.get("[id^=headlessui-combobox-input-]").eq(1).should("have.value", ACCOUNT_NAME);
    });

    // Check the is protected field
    cy.get("#is\\ protected").click();

    cy.get("#is\\ protected").should("be.checked");

    cy.intercept("/graphql/main").as("Request");

    cy.contains("button", "Save").click();

    cy.wait("@Request");
  });

  it("should verify the prefilled object's metadata", function () {
    // Access the interfaces view
    cy.contains("Interface").click();

    // Access an interface
    cy.contains(ETHERNET_NAME).first().click();

    // Open the metadata panel
    cy.get(".sm\\:p-0").within(() => {
      cy.contains("Status")
        .parent()
        .within(() => {
          cy.get("[data-cy='metadata-button']").click();
        });
    });

    // Check the source
    cy.get(".w-80 > :nth-child(4)").should("exist");

    // Edit the metadata
    cy.get(".w-80 > :nth-child(1) > .rounded-md").click();

    // Is visible
    cy.get("#is\\ visible").should("be.checked");

    // Is protected
    cy.get("#is\\ protected").should("be.checked");

    // Owner select
    cy.get(".grid-cols-1 > :nth-child(1) > .grid").within(() => {
      // First select should exist
      cy.get("[id^=headlessui-combobox-input-]").first().should("have.value", ACCOUNT);

      // Second select should exist
      cy.get("[id^=headlessui-combobox-input-]").eq(1).should("have.value", ACCOUNT_NAME);
    });
  });
});
