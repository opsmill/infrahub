/// <reference types="cypress" />

import { MockedProvider } from "@apollo/client/testing";
import React from "react";

describe("Config fetch", () => {
  beforeEach(function () {
    cy.fixture("login").as("login");
    cy.fixture("config").as("config");
    cy.fixture("info").as("info");
    cy.fixture("schema").as("schema");
    cy.fixture("schemaSummary").as("schemaSummary");
    cy.fixture("menu").as("menu");
    cy.fixture("branches").as("branches");
  });

  it("should login and load the config", function () {
    cy.viewport(1920, 1080);

    cy.intercept("POST", "/api/auth/login", this.login).as("login");
    cy.intercept("GET", "/api/config", this.config).as("getConfig");
    cy.intercept("GET", "/api/info", this.info).as("getInfo");
    cy.intercept("GET", "/api/schema*", this.schema).as("getSchema");
    cy.intercept("GET", "/api/schema/summary*", this.schema).as("getSchemaSummary");
    cy.intercept("GET", "/api/menu*", this.menu).as("getMenu");
    cy.intercept("POST", "/graphql/main", this.branches).as("branches");

    cy.mount(<MockedProvider addTypename={false}>{/*<App />*/}</MockedProvider>);
  });
});
