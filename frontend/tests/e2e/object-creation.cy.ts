/// <reference types="cypress" />

import { expect } from "chai";
import { NEW_ACCOUNT } from "../mocks/e2e/accounts";
import { ADMIN_CREDENTIALS, waitFor } from "../utils";

describe("Object creation and deletion", () => {
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

    // Wait after creation, the body data should contain an object
    waitFor("@Request", (interception) => {
      console.log(
        "### !!interception?.response?.body?.data?.CoreAccountCreate: ",
        !!interception?.response?.body?.data?.CoreAccountCreate
      );
      return !!interception?.response?.body?.data?.CoreAccountCreate;
    }).then(() => {
      console.log("### THEN 1");

      // Wait after refetch, the body data should contain an object
      waitFor("@Request", (interception) => {
        console.log(
          "### !!interception?.response?.body?.data?.CoreAccount: ",
          !!interception?.response?.body?.data?.CoreAccount
        );
        return !!interception?.response?.body?.data?.CoreAccount;
      }).then(() => {
        console.log("### THEN 2");

        // Get the previous number from the previous request
        cy.get("@itemsNumber").then((itemsNumber) => {
          console.log("### itemsNumber: ", itemsNumber);
          // Get the new number
          cy.get("div.flex > .text-sm > :nth-child(3)").then((element) => {
            const newItemsNumber = parseInt(element.text());
            console.log("### newItemsNumber: ", newItemsNumber);

            // The new number should be old number + 1
            expect(newItemsNumber).to.be.eq(itemsNumber + 1);
          });
        });
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

    // Wait after deletion, the body data should contain an object
    waitFor("@Request", (interception) => {
      console.log(
        "### !!interception?.response?.body?.data?.CoreAccountDelete: ",
        !!interception?.response?.body?.data?.CoreAccountDelete
      );
      return !!interception?.response?.body?.data?.CoreAccountDelete;
    }).then(() => {
      console.log("### THEN 1");

      // Wait after refetch, the body data should contain an object
      waitFor("@Request", (interception) => {
        console.log(
          "### !!interception?.response?.body?.data?.CoreAccount: ",
          !!interception?.response?.body?.data?.CoreAccount
        );
        return !!interception?.response?.body?.data?.CoreAccount;
      }).then(() => {
        console.log("### THEN 2");

        // Get the previous number from the previous request
        cy.get("@itemsNumber").then((itemsNumber) => {
          console.log("### itemsNumber: ", itemsNumber);
          // Get the new number
          cy.get("div.flex > .text-sm > :nth-child(3)").then((element) => {
            const newItemsNumber = parseInt(element.text());
            console.log("### newItemsNumber: ", newItemsNumber);

            // The new number should be old number + 1
            expect(newItemsNumber).to.be.eq(itemsNumber - 1);
          });
        });
      });
    });
  });
});
