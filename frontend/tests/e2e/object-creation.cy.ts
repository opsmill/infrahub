/// <reference types="cypress" />

import { expect } from "chai";
import { NEW_ACCOUNT } from "../mocks/e2e/accounts";
import { ADMIN_CREDENTIALS } from "../utils";

describe("Object creation and deletion", () => {
  beforeEach(function () {
    cy.login(ADMIN_CREDENTIALS.username, ADMIN_CREDENTIALS.password);

    cy.visit("/");
  });

  it("should create an object", function () {
    // Access the account view
    cy.contains("Account").click();

    // Get the actual number of items
    cy.get("div.flex > .text-sm > :nth-child(3)").then((element) => {
      const itemsNumber = parseInt(element.text());

      cy.wrap(itemsNumber).as("itemsNumber");
    });

    // Open the create form
    cy.get(".sm\\:flex.py-4").within(() => {
      cy.get(".p-2").click();
    });

    // Type the name
    cy.get(".grid > :nth-child(1) > .relative > .block").type(NEW_ACCOUNT.name);

    // Type the password
    cy.get(":nth-child(2) > .relative > .block").type(NEW_ACCOUNT.password);

    // Click save
    cy.get(".justify-end > .bg-custom-blue-700").click();

    // Wait for the object to be created (the save button should not exist)
    cy.get(".justify-end > .bg-custom-blue-700").should("not.exist");

    // Get the previous number from the previous request
    cy.get("@itemsNumber").then((itemsNumber) => {
      // Get the new number
      cy.get("div.flex > .text-sm > :nth-child(3)").then((element) => {
        const itemsNewNumber = parseInt(element.text());

        // The new number should be old number + 1
        expect(itemsNewNumber).to.be.eq(itemsNumber + 1);
      });
    });
  });

  it("should delete an object", function () {
    // Access the account view
    cy.contains("Account").click();

    // Get the actual number of items
    cy.get("div.flex > .text-sm > :nth-child(3)").then((element) => {
      const itemsNumber = parseInt(element.text());

      cy.wrap(itemsNumber).as("itemsNumber");
    });

    // Get the delete button for the new account
    cy.contains(NEW_ACCOUNT.name).scrollIntoView();
    cy.contains(NEW_ACCOUNT.name).siblings(".py-3").click();

    // The account name should be displayed in the delete modal
    cy.get("b").should("include.text", NEW_ACCOUNT.name);

    // Delete the object
    cy.get(".bg-red-600").click();

    // Wait the request
    cy.contains("Delete").should("not.exist");

    // Get the previous number from the previous request
    cy.get("@itemsNumber").then((itemsNumber) => {
      // Get the new number
      cy.get("div.flex > .text-sm > :nth-child(3)").then((element) => {
        const itemsNewNumber = parseInt(element.text());

        // The new number should be old number - 1
        expect(itemsNewNumber).to.be.eq(itemsNumber - 1);
      });
    });
  });
});
