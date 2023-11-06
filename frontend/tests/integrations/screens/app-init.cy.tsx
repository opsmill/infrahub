/// <reference types="cypress" />

import { MockedProvider } from "@apollo/client/testing";
import React from "react";
import App from "../../../src/App";

describe("Config fetch", () => {
  beforeEach(function () {
    cy.fixture("login").as("login");
    cy.fixture("config").as("config");
    cy.fixture("schema").as("schema");
  });

  it("should login and load the config", function () {
    cy.viewport(1920, 1080);

    cy.intercept("POST", "/api/auth/login", this.login).as("login");

    cy.intercept("GET", "/api/config", this.config).as("getConfig");

    cy.intercept("GET", "/api/schema", this.schema).as("getSchema");

    cy.mount(
      <MockedProvider addTypename={false}>
        <App />
      </MockedProvider>
    );

    cy.get(":nth-child(1) > .relative > .block").type("test", { delay: 0 });

    cy.get(":nth-child(2) > .relative > .block").type("test", { delay: 0 });

    cy.get(".justify-end > .rounded-md").click();

    cy.wait("@login").then(({ response }) => {
      expect(response?.body?.access_token).to.exist;
    });

    cy.wait("@getSchema").then(({ response }) => {
      const schemaArray = response?.body?.nodes;

      expect(schemaArray).to.have.lengthOf(1);
    });

    cy.intercept("GET", "/api/menu", this.menu).as("getMenu");

    cy.wait("@getMenu").then(() => {
      // Check if the Objects menu is existing
      cy.get("[data-cy='sidebar-menu']").within(() => {
        cy.contains("Objects").should("exist");
      });
    });
  });
});
