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

    // Intercept mutation
    cy.intercept("/graphql/main").as("AddRequest");

    // Intercept refetch
    cy.intercept("/graphql/main").as("RefetchRequest");

    // Click save
    cy.get(".justify-end > .bg-custom-blue-700").click();

    // Wait for the mutation to succeed
    cy.wait("@AddRequest");

    // Wait refetch
    cy.wait("@RefetchRequest", { timeout: 10000 });

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

    // Intercept mutation
    cy.intercept("/graphql/main").as("DeleteRequest");

    // Intercept refetch
    cy.intercept("/graphql/main").as("RefetchRequest");

    // Delete the object
    cy.get(".bg-red-600").click();

    // Wait for the mutation to succeed
    cy.wait("@DeleteRequest");

    // Wait refetch
    cy.wait("@RefetchRequest", { timeout: 10000 });

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
