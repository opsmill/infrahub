/// <reference types="cypress" />

import { NEW_ACCOUNT } from "../mocks/e2e/accounts";
import { ADMIN_CREDENTIALS, waitFor } from "../utils";

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
    cy.contains("Account").click();

    // Get the actual number of items
    cy.get("div.flex > .text-sm > :nth-child(3)").then((element) => {
      itemsNumber = parseInt(element.text());
    });

    // Open the create form
    cy.get("[data-cy='create']").click();

    // Type the name
    cy.get(".grid > :nth-child(1) > .relative > .block").type(NEW_ACCOUNT.name, { delay: 0 });

    // Type the password
    cy.get(":nth-child(2) > .relative > .block").type(NEW_ACCOUNT.password, { delay: 0 });

    // Click save
    cy.get(".justify-end > .bg-custom-blue-700").click();

    // Wait after refetch, the body data should contain an object
    waitFor(
      "@Request",
      (interception) => interception?.response?.body?.data?.CoreAccount?.count > itemsNumber
    ).then(() => {
      const newText = itemsNumber + 1;

      // Get the new number
      cy.get("div.flex > .text-sm > :nth-child(3)").should("have.text", newText);
    });
  });

  it("should delete an object", function () {
    // Access the account view
    cy.contains("Account").click();

    // Get the actual number of items
    cy.get("div.flex > .text-sm > :nth-child(3)").then((element) => {
      itemsNumber = parseInt(element.text());
    });

    // Get the delete button for the new account
    cy.contains(NEW_ACCOUNT.name).scrollIntoView();
    cy.contains(NEW_ACCOUNT.name)
      .siblings("td")
      .last()
      .within(() => cy.get("[data-cy='delete']").click());

    // The account name should be displayed in the delete modal
    cy.get("b").should("include.text", NEW_ACCOUNT.name);

    // Delete the object
    cy.get(".bg-red-600").click();

    // Wait after refetch, the body data should contain an object
    waitFor(
      "@Request",
      (interception) => interception?.response?.body?.data?.CoreAccount?.count === itemsNumber
    ).then(() => {
      const newText = itemsNumber - 1;

      // Get the new number
      cy.get("div.flex > .text-sm > :nth-child(3)").should("have.text", newText);
    });
  });
});
