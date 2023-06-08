/// <reference types="cypress" />

import { gql } from "@apollo/client";
import { MockedProvider } from "@apollo/client/testing";
import React from "react";
import { Route, Routes } from "react-router-dom";
import {
  deviceDetailsMocksData,
  deviceDetailsMocksDataAfterUpdate,
  deviceDetailsMocksId,
  deviceDetailsMocksQuery,
  deviceDetailsMocksSchema,
  deviceDetailsName,
  deviceDetailsNewName,
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
  // Initial render
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
  // After mutation
  {
    request: {
      query: gql`
        ${deviceDetailsMocksQuery}
      `,
    },
    result: {
      data: deviceDetailsMocksDataAfterUpdate,
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

describe("Object details", () => {
  beforeEach(function () {
    cy.fixture("device-detail-update-name").as("mutation");
  });

  it("should fetch the object details, open the edit form and update the object name", function () {
    cy.viewport(1920, 1080);

    cy.intercept("POST", "/graphql/main ", this.mutation).as("mutate");

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

    // Check the initial name
    cy.get(".rounded-md").should("have.text", "Edit");

    // Click on the edit button
    cy.get(".rounded-md").click();

    // Check if the field has the correct initial value
    cy.get(".grid > :nth-child(1) > .relative > .block").should("have.value", deviceDetailsName);

    // Clear and type the new name
    cy.get(".grid > :nth-child(1) > .relative > .block").clear();
    cy.get(".grid > :nth-child(1) > .relative > .block").type(deviceDetailsNewName);

    // Verify that the name is correctly set
    cy.get(".grid > :nth-child(1) > .relative > .block").should("have.value", deviceDetailsNewName);

    // Verify that the button is not in a loading state
    cy.get(".bg-blue-500").should("have.text", "Save");

    // Submit the form
    cy.get(".bg-blue-500").click();

    // Wait for the mutation to be done
    cy.wait("@mutate");

    // Verify that the data is refetched
    cy.get(":nth-child(2) > div.flex > .mt-1").should("have.text", deviceDetailsNewName);
  });
});
