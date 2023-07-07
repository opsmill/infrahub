/// <reference types="cypress" />

import { gql } from "@apollo/client";
import { MockedProvider } from "@apollo/client/testing";
import React from "react";
import { Route, Routes } from "react-router-dom";
import { withAuth } from "../../../src/decorators/withAuth";
import ObjectDetails from "../../../src/screens/object-item-details/object-item-details-paginated";
import { configState } from "../../../src/state/atoms/config.atom";
import { schemaState } from "../../../src/state/atoms/schema.atom";
import { configMocks } from "../../mocks/data/config";
import {
  deviceDetailsMocksData,
  deviceDetailsMocksDataAfterUpdate,
  deviceDetailsMocksId,
  deviceDetailsMocksQuery,
  deviceDetailsMocksSchema,
  deviceDetailsName,
  deviceDetailsNewName,
  deviceDetailsUpdateMocksData,
  deviceDetailsUpdateMocksQuery,
} from "../../mocks/data/devices";
import { TestProvider } from "../../mocks/jotai/atom";

// URL for the current view
const mockedUrl = `/objects/Device/${deviceDetailsMocksId}`;

// Path that will match the route to display the component
const mockedPath = "/objects/:objectname/:objectid";

// Mock the apollo query and data
const mocks: any[] = [
  // Details query
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
  // Update query
  {
    request: {
      query: gql`
        ${deviceDetailsUpdateMocksQuery}
      `,
    },
    result: {
      data: deviceDetailsUpdateMocksData,
    },
  },
  // Details query
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
  // Update query
  {
    request: {
      query: gql`
        ${deviceDetailsUpdateMocksQuery}
      `,
    },
    result: {
      data: deviceDetailsUpdateMocksData,
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

const AuthenticatedObjectItems = withAuth(ObjectDetails);

// Provide the initial value for jotai
const ObjectDetailsProvider = () => {
  return (
    <TestProvider
      initialValues={[
        [schemaState, deviceDetailsMocksSchema],
        [configState, configMocks],
      ]}>
      <AuthenticatedObjectItems />
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
          <Route element={<ObjectDetailsProvider />} path={mockedPath} />
        </Routes>
      </MockedProvider>,
      {
        // Add iniital route for the app router, to display the current items view
        routerProps: {
          initialEntries: [mockedUrl],
        },
      }
    );

    // Click on the edit button
    cy.get(".flex-col > .bg-custom-white > :nth-child(2) > :nth-child(1)").click();

    // Check if the field has the correct initial value
    cy.get(".grid > :nth-child(1) > .relative > .block").should("have.value", deviceDetailsName);

    // Clear and type the new name
    cy.get(".grid > :nth-child(1) > .relative > .block").clear();
    cy.get(".grid > :nth-child(1) > .relative > .block").type(deviceDetailsNewName);

    // Verify that the name is correctly set
    cy.get(".grid > :nth-child(1) > .relative > .block").should("have.value", deviceDetailsNewName);

    // Verify that the button is not in a loading state
    cy.get(".bg-custom-blue-700").should("have.text", "Save");

    // Submit the form
    cy.get(".bg-custom-blue-700").click();

    // Wait for the mutation to be done
    cy.wait("@mutate");

    // Verify that the data is refetched
    cy.get(":nth-child(2) > div.flex > .mt-1").should("have.text", deviceDetailsNewName);
  });
});
