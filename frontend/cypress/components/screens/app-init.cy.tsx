/// <reference types="cypress" />

import React from "react";
import App from "../../../src/App";

describe("Config fetch", () => {
  beforeEach(function () {
    cy.fixture("config").as("config");
    cy.fixture("schema").as("schema");
  });

  it("should load the schema + config", function () {
    cy.viewport(1920, 1080);

    cy.intercept("GET", "/config", this.config).as("getConfig");
    cy.intercept("GET", "/schema", this.schema).as("getSchema");

    cy.mount(<App />);

    cy.wait("@getConfig").then(({ response }) => {
      expect(response?.body?.experimental_features?.test).to.be.true;
    });

    cy.wait("@getSchema").then(({ response }) => {
      const schemaArray = response?.body;
      expect(schemaArray).to.have.lengthOf(1);
    });
  });
});
