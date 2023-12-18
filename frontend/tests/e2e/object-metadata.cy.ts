/// <reference types="cypress" />

import { ADMIN_CREDENTIALS } from "../utils";

const ETHERNET_DESCRIPTION = "Connected to dfw1-edge2 Ethernet1";

const ACCOUNT = "Account";

const ACCOUNT_NAME = "Operation Team";

describe("Object update", () => {
  beforeEach(function () {
    cy.login(ADMIN_CREDENTIALS.username, ADMIN_CREDENTIALS.password);

    cy.visit("/");
  });

  it("should access the object's metadata", function () {
    // Access the interfaces view
    cy.contains("Interface").click();

    // Access an interface
    cy.contains(ETHERNET_DESCRIPTION).click();

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
    cy.get(":nth-child(3) > .flex-col > .relative > .w-4").should("be.checked");

    // Is protected
    cy.get(":nth-child(4) > .flex-col > .relative > .w-4").should("not.be.checked");

    // Owner select
    cy.get(".grid-cols-1 > :nth-child(1) > .grid").within(() => {
      // The first select should exists
      cy.get("[id^=headlessui-combobox-input-]").first();

      // Open the select
      cy.get("[id^=headlessui-combobox-button-]").click();

      // Check if the options have a length of 3
      cy.get("[id^=headlessui-combobox-options-]").find("li").should("have.length", 3);

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

    // Check the is proteced field
    cy.get(":nth-child(4) > .flex-col > .relative > .w-4").click();

    cy.get(":nth-child(4) > .flex-col > .relative > .w-4").should("be.checked");

    cy.get(".justify-end").within(() => {
      cy.intercept("/graphql/main").as("Request");

      cy.contains("Save").click();

      cy.wait("@Request");
    });
  });

  it("should verify the prefilled object's metadata", function () {
    // Access the interfaces view
    cy.contains("Interface").click();

    // Access an interface
    cy.contains(ETHERNET_DESCRIPTION).click();

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
    cy.get(":nth-child(3) > .flex-col > .relative > .w-4").should("be.checked");

    // Is protected
    cy.get(":nth-child(4) > .flex-col > .relative > .w-4").should("be.checked");

    // Owner select
    cy.get(".grid-cols-1 > :nth-child(1) > .grid").within(() => {
      // First select should exist
      cy.get("[id^=headlessui-combobox-input-]").first().should("have.value", ACCOUNT);

      // Second select should exist
      cy.get("[id^=headlessui-combobox-input-]").eq(1).should("have.value", ACCOUNT_NAME);
    });
  });
});
