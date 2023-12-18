/// <reference types="cypress" />

import { gql } from "@apollo/client";
import { MockedProvider } from "@apollo/client/testing";
import React from "react";
import { Route, Routes } from "react-router-dom";
import ObjectItems from "../../../src/screens/object-items/object-items-paginated";
import { schemaFamily } from "../../../src/state/atoms/schema.atom";
import {
  graphqlQueriesMocksData,
  graphqlQueriesMocksQuery,
  graphqlQueriesMocksQueryWithLimit,
} from "../../mocks/data/graphqlQueries";
import { schemaMocks } from "../../mocks/data/schema";

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
  // After limit update
  {
    request: {
      query: gql`
        ${graphqlQueriesMocksQueryWithLimit}
      `,
    },
    result: {
      data: graphqlQueriesMocksData,
    },
  },
];

// Provide the initial value for jotai
schemaMocks.forEach((s) => {
  schemaFamily(s);
});

describe("List screen", () => {
  it("should fetch items and render list", () => {
    cy.viewport(1920, 1080);

    // Mount the view with the default route and the mocked data
    cy.mount(
      <MockedProvider mocks={mocks} addTypename={false}>
        <Routes>
          <Route element={<ObjectItems />} path={mockedPath} />
        </Routes>
      </MockedProvider>,
      {
        // Add initial route for the app router, to display the current items view
        routerProps: {
          initialEntries: [mockedUrl],
        },
      }
    );

    // Should check that the last item in pagination is page number 100
    cy.get(":nth-child(7) > .cursor-pointer").should("have.text", "100");

    // Should display the last item for the current page
    cy.get(":nth-child(10) > :nth-child(1)").should("exist");

    // Should display a tag in the tags list for the 4th item in the list
    cy.get(":nth-child(4) > :nth-child(4) > div.flex > :nth-child(3)").should(
      "have.text",
      "maroon"
    );

    // Select the limit 50
    cy.get("[id^=headlessui-combobox-button-]").click();
    cy.contains("50").click();

    // The last page should be the number 20
    cy.get(":nth-child(7) > .cursor-pointer").should(
      "have.text",
      Math.ceil(graphqlQueriesMocksData.CoreGraphQLQuery.count / 50)
    );
  });
});
