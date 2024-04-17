/// <reference types="cypress" />

import { gql } from "@apollo/client";
import { MockedProvider } from "@apollo/client/testing";
import React from "react";
import { Route, Routes } from "react-router-dom";
import ObjectItems from "../../../src/screens/object-items/object-items-paginated";
import { genericsState, schemaState } from "../../../src/state/atoms/schema.atom";
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
const mockedPath = "/objects/:objectname";

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
      variables: { offset: 0, limit: 10 },
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
      <ObjectItems />
    </TestProvider>
  );
};

describe("List screen", () => {
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

    // last pagination number
    cy.get(":nth-child(7) > .cursor-pointer").should("have.text", "100");

    // Should display the last item for the current page
    cy.contains("query-0010").should("be.visible");

    // Should display a tag in the tags list for the 4th item in the list
    cy.get("[data-cy='object-table-row']")
      .first()
      .within(() => {
        cy.contains("span", "maroon").should("be.visible");
      });

    // Select the limit 50
    cy.get("[id^=headlessui-combobox-button-]").click();
    cy.contains("50").click();

    // The last page should be the number 20
    cy.get(":nth-child(7) > .cursor-pointer").should(
      "have.text",
      Math.ceil(graphqlQueriesMocksData.CoreGraphQLQuery.count / 50)
    );
  });

  it("should not display add open panel when object is generic", () => {
    cy.viewport(1920, 1080);
    const GenericItemsProvider = () => {
      return (
        <TestProvider
          initialValues={[
            [schemaState, []],
            [genericsState, schemaMocks],
          ]}>
          <ObjectItems />
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

    // Should check that the last item in pagination is page number 100
    cy.get(":nth-child(7) > .cursor-pointer").should("have.text", "100");

    cy.get("[data-cy='create']").should("not.exist");
  });
});
