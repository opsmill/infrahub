/// <reference types="cypress" />

import { expect } from "chai";
import { NEW_ACCOUNT } from "../mocks/e2e/accounts";
import { ADMIN_CREDENTIALS } from "../utils";

describe("Object creation", () => {
  beforeEach(function () {
    cy.login(ADMIN_CREDENTIALS.username, ADMIN_CREDENTIALS.password);

    cy.visit("/");
  });

  it("should create an object", function () {
    // Access the account view
    cy.contains("Account").click();

    // Get the actual number of items
    cy.get("div.flex > .text-sm > :nth-child(3)").then((element) => {
      cy.wrap(element).as("itemsNumber");
    });

    // Open the create form
    cy.get(".p-2").click();

    // Type the name
    cy.get(".grid > :nth-child(1) > .relative > .block").type(NEW_ACCOUNT.name);

    // Type the password
    cy.get(":nth-child(2) > .relative > .block").type(NEW_ACCOUNT.password);

    // Click save
    cy.get(".mt-6 > .bg-custom-blue-700").click();

    // Wait for the object to be created (the save button should not exist)
    cy.get(".mt-6 > .bg-custom-blue-700").should("not.exist");

    // Get the previous number from the previous request
    cy.get("@itemsNumber").then((element) => {
      const itemsNumber = parseInt(element.text());

      cy.log("# itemsNumber: ", itemsNumber);

      // Get the new number
      cy.get("div.flex > .text-sm > :nth-child(3)").then((element) => {
        const itemsNewNumber = parseInt(element.text());
        cy.log("itemsNewNumber: ", itemsNewNumber);

        cy.log("itemsNumber + 1: ", itemsNumber + 1);
        // The new number should be old number + 1
        expect(itemsNewNumber).to.be.eq(itemsNumber + 1);
      });
    });
  });
});
