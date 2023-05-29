/// <reference types="cypress" />

import React from "react";
import App from "../../../src/App";

describe("Config fetch", () => {
  it("should load the config", () => {
    cy.viewport(1920, 1080);

    // Intercept and wait config query
    cy.fixture("config").then((config) => {
      cy.log("config:", config);
      cy.intercept("GET", "/config", config).as("getConfig");
    });

    cy.mount(<App />);

    cy.wait("@getConfig").then(({ response }) => {
      expect(response?.body?.experimental_features?.test).to.be.true;
    });
  });

  it("should load the schema", () => {
    cy.viewport(1920, 1080);

    // Intercept and wait schema query
    cy.fixture("schema").then((schema) => {
      cy.log("schema:", schema);
      cy.intercept("GET", "/schema", schema).as("getSchema");
    });

    cy.mount(<App />);

    cy.wait("@getSchema").then(({ response }) => {
      const schemaArray = response?.body;
      expect(schemaArray).to.have.lengthOf(1);
    });
  });
});
