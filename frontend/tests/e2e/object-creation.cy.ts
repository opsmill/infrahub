/// <reference types="cypress" />

import { ADMIN_CREDENTIALS } from "../constants";
import { NEW_ACCOUNT } from "../mocks/e2e/accounts";
import { waitFor } from "../utils";

describe("Object creation and deletion", () => {
  let itemsNumber = 0;

  beforeEach(function () {
    cy.login(ADMIN_CREDENTIALS.username, ADMIN_CREDENTIALS.password);

    cy.visit("/");

    // Intercept mutation
    cy.intercept("POST", "/graphql/main").as("Request");
  });

  it("should create an object", function () {
    // Access the account view
    cy.get("[href='/objects/CoreAccount'").click();

    // Get the actual number of items
    cy.get(".hidden > div.flex > .text-sm > :nth-child(2)").then((element) => {
      itemsNumber = parseInt(element.text());

      // Open the create form
      cy.get("[data-cy='create']").click();

      // Type the name
      cy.get(".grid > :nth-child(1) > .relative > .block").type(NEW_ACCOUNT.name, {
        delay: 0,
        force: true,
      });
      cy.get(".grid > :nth-child(1) > .relative > .block").should("have.value", NEW_ACCOUNT.name);

      // Type the password
      cy.get(".grid > :nth-child(2) > .relative > .block").type(NEW_ACCOUNT.password, {
        delay: 0,
        force: true,
      });
      cy.get(".grid > :nth-child(2) > .relative > .block").should(
        "have.value",
        NEW_ACCOUNT.password
      );

      // Click save
      cy.get("[data-cy='submit-form']").click();

      // Wait after refetch, the body data should contain an object
      waitFor("@Request", (interception) => {
        const count = parseInt(interception?.response?.body?.data?.CoreAccount?.count);
        return count > itemsNumber;
      }).then(() => {
        const newText = itemsNumber + 1;

        // Get the new number
        cy.get(".hidden > div.flex > .text-sm > :nth-child(2)").should("have.text", newText);
      });
    });
  });

  it("should delete an object", function () {
    // Access the account view
    cy.get("[href='/objects/CoreAccount'").click();

    // Get the actual number of items
    cy.get(".hidden > div.flex > .text-sm > :nth-child(2)").then((element) => {
      itemsNumber = parseInt(element.text());

      // Get the delete button for the new account
      cy.contains(NEW_ACCOUNT.name).scrollIntoView();
      cy.contains(NEW_ACCOUNT.name)
        .parent()
        .siblings("td")
        .last()
        .within(() => cy.get("[data-cy='delete']").click());

      // The account name should be displayed in the delete modal
      cy.get("b").should("include.text", NEW_ACCOUNT.name);

      // Delete the object
      cy.get(".bg-red-600").click();

      // Wait after refetch, the body data should contain an object
      waitFor("@Request", (interception) => {
        const count = parseInt(interception?.response?.body?.data?.CoreAccount?.count);
        return count < itemsNumber;
      }).then(() => {
        const newText = itemsNumber - 1;

        // Get the new number
        cy.get("div.flex > .text-sm > :nth-child(3)").should("have.text", newText);
      });
    });
  });
});
