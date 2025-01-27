/// <reference types="cypress" />

import { gql } from "@apollo/client";
import { MockedProvider } from "@apollo/client/testing";
import { Route, Routes } from "react-router-dom";
import { genericsState, schemaState } from "../../../src/entities/schema/stores/schema.atom";
import { ObjectItemsPage } from "../../../src/pages/objects/object-items";
import {
  graphqlQueriesMocksData,
  graphqlQueriesMocksQuery,
  graphqlQueriesMocksQueryWithLimit,
} from "../../mocks/data/graphqlQueries";
import { schemaMocks } from "../../mocks/data/schema";
import { TestProvider } from "../../mocks/jotai/atom";

// URL for the current view
const mockedUrl = "/objects/CoreGraphQLQuery";

// Path that will match the route to display the component
const mockedPath = "/objects/:objectKind";

// Mock the apollo query and data
const mocks: any[] = [
  // Initial query
  {
    request: {
      query: gql`
        ${graphqlQueriesMocksQuery}
      `,
      variables: { offset: 0, limit: 10 },
    },
    result: {
      data: graphqlQueriesMocksData,
    },
  },
  // After limit update
  {
    request: {
      query: gql`
        ${graphqlQueriesMocksQueryWithLimit}
      `,
      variables: { offset: 0, limit: 50 },
    },
    result: {
      data: graphqlQueriesMocksData,
    },
  },
];

// Provide the initial value for jotai
const ObjectItemsProvider = () => {
  return (
    <TestProvider initialValues={[[schemaState, schemaMocks]]}>
      <ObjectItemsPage />
    </TestProvider>
  );
};

describe("List screen", () => {
  beforeEach(() => {
    cy.fixture("config").then(function (json) {
      cy.intercept("GET", "/api/config", json).as("config");
    });
  });

  it("should fetch items and render list", () => {
    cy.viewport(1920, 1080);

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

    // Should check that the last item in pagination is page number 100
    cy.get("[data-cy='create']").should("exist");

    // Should display the last item for the current page
    cy.contains("topology_info").should("be.visible");

    // Should display a tag in the tags list for the 4th item in the list
    cy.get("[data-testid='object-items']").within(() => {
      cy.contains("demo-edge").should("be.visible");
    });
  });

  it("should display add open panel when object is generic", () => {
    cy.viewport(1920, 1080);
    const GenericItemsProvider = () => {
      return (
        <TestProvider
          initialValues={[
            [schemaState, []],
            [genericsState, schemaMocks],
          ]}
        >
          <ObjectItemsPage />
        </TestProvider>
      );
    };

    // Mount the view with the default route and the mocked data
    cy.mount(
      <MockedProvider mocks={mocks} addTypename={false}>
        <Routes>
          <Route element={<GenericItemsProvider />} path={mockedPath} />
        </Routes>
      </MockedProvider>,
      {
        // Add iniital route for the app router, to display the current items view
        routerProps: {
          initialEntries: [mockedUrl],
        },
      }
    );

    cy.get("[data-cy='create']").should("exist");
  });
});
