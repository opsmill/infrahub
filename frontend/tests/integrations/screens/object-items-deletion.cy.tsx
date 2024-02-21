/// <reference types="cypress" />

import { gql } from "@apollo/client";
import { MockedProvider } from "@apollo/client/testing";
import React from "react";
import { Route, Routes } from "react-router-dom";
import { ACCESS_TOKEN_KEY } from "../../../src/config/constants";
import ObjectItems from "../../../src/screens/object-items/object-items-paginated";
import { configState } from "../../../src/state/atoms/config.atom";
import { schemaState } from "../../../src/state/atoms/schema.atom";
import { mockedToken } from "../../fixtures/auth";
import { configMocks } from "../../mocks/data/config";
import {
  graphqlQueriesMocksData,
  graphqlQueriesMocksDataDeleted,
  graphqlQueriesMocksQuery,
  objectToDelete,
} from "../../mocks/data/graphqlQueries";
import { schemaMocks } from "../../mocks/data/schema";
import { TestProvider } from "../../mocks/jotai/atom";
import { AuthProvider } from "../../../src/decorators/auth";

// URL for the current view
const mockedUrl = "/objects/CoreGraphQLQuery";

// Path that will match the route to display the component
const mockedPath = "/objects/:objectname";

// Mock the apollo query and data
const mocks: any[] = [
  // Initial query
  {
    request: {
      query: gql`
        ${graphqlQueriesMocksQuery}
      `,
    },
    result: {
      data: graphqlQueriesMocksData,
    },
  },
  // After deletion
  {
    request: {
      query: gql`
        ${graphqlQueriesMocksQuery}
      `,
    },
    result: {
      data: graphqlQueriesMocksDataDeleted,
    },
  },
];

const AuthenticatedObjectItems = () => (
  <AuthProvider>
    <ObjectItems />
  </AuthProvider>
);

// Provide the initial value for jotai
const ObjectItemsProvider = () => {
  return (
    <TestProvider
      initialValues={[
        [schemaState, schemaMocks],
        [configState, configMocks],
      ]}>
      <AuthenticatedObjectItems />
    </TestProvider>
  );
};

describe("List screen", () => {
  beforeEach(function () {
    cy.fixture("device-items-delete").as("delete");

    localStorage.setItem(ACCESS_TOKEN_KEY, mockedToken);
  });

  it("should fetch items and render list", function () {
    cy.viewport(1920, 1080);

    cy.fixture("device-detail-update-name").as("delete");

    cy.intercept("POST", "/graphql/main ", this.delete).as("delete");

    // Mount the view with the default route and the mocked data
    cy.mount(
      <MockedProvider mocks={mocks} addTypename={false}>
        <Routes>
          <Route element={<ObjectItemsProvider />} path={mockedPath} />
        </Routes>
      </MockedProvider>,
      {
        // Add iniital route for the app router, to display the current items view
        routerProps: {
          initialEntries: [mockedUrl],
        },
      }
    );

    cy.get("[data-cy='object-table-row']")
      .first()
      .within(() => {
        cy.contains(objectToDelete).should("be.visible");

        // Open delete modal
        cy.get("[data-cy='delete']").click();
      });

    cy.get("[data-cy='modal-delete']").within(() => {
      // The object should be correctly displayed
      cy.contains(objectToDelete).should("be.visible");

      // Submit
      cy.contains("button", "Delete").click();
    });

    // Wait for the mutation to be done
    cy.wait("@delete");

    cy.get("[data-cy='object-table-row']").should("not.have.text", objectToDelete);
  });
});
