/// <reference types="cypress" />

import { gql } from "@apollo/client";
import { MockedProvider } from "@apollo/client/testing";
import React from "react";
import { Route, Routes } from "react-router-dom";
import {
  deviceDetailsMocksASNName,
  deviceDetailsMocksData,
  deviceDetailsMocksId,
  deviceDetailsMocksOwnerName,
  deviceDetailsMocksQuery,
  deviceDetailsMocksSchema,
  deviceDetailsMocksTagName,
} from "../../../mocks/data/devices";
import { TestProvider } from "../../../mocks/jotai/atom";
import ObjectDetails from "../../../src/screens/object-item-details/object-item-details-paginated";
import { schemaState } from "../../../src/state/atoms/schema.atom";

// URL for the current view
const graphqlQueryItemsUrl = `/objects/device/${deviceDetailsMocksId}`;

// Path that will match the route to display the component
const graphqlQueryItemsPath = "/objects/:objectname/:objectid";

// Mock the apollo query and data
const mocks: any[] = [
  {
    request: {
      query: gql`
        ${deviceDetailsMocksQuery}
      `,
    },
    result: {
      data: deviceDetailsMocksData,
    },
  },
];

// Provide the initial value for jotai
const ObjectDetailsProvider = () => {
  return (
    <TestProvider initialValues={[[schemaState, deviceDetailsMocksSchema]]}>
      <ObjectDetails />
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
          <Route element={<ObjectDetailsProvider />} path={graphqlQueryItemsPath} />
        </Routes>
      </MockedProvider>,
      {
        // Add iniital route for the app router, to display the current items view
        routerProps: {
          initialEntries: [graphqlQueryItemsUrl],
        },
      }
    );

    cy.get(":nth-child(8) > .py-4 > .mt-1 > .cursor-pointer").should(
      "have.text",
      deviceDetailsMocksASNName
    );

    cy.get(":nth-child(8) > .py-4 > .mt-1 > .relative").click();

    cy.get(":nth-child(5) > .underline").should("have.text", deviceDetailsMocksOwnerName);

    cy.get(".sm\\:col-span-2 > :nth-child(1) > .cursor-pointer").should(
      "have.text",
      deviceDetailsMocksTagName
    );
  });
});
