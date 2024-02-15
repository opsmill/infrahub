/// <reference types="cypress" />

import { gql } from "@apollo/client";
import { MockedProvider } from "@apollo/client/testing";
import React from "react";
import { Route, Routes } from "react-router-dom";
import ObjectDetails from "../../../src/screens/object-item-details/object-item-details-paginated";
import { genericsState, schemaState } from "../../../src/state/atoms/schema.atom";
import {
  deviceDetailsInterfacesMocksData,
  deviceDetailsInterfacesMocksQuery,
  deviceDetailsMocksData,
  deviceDetailsMocksGenerics,
  deviceDetailsMocksId,
  deviceDetailsMocksQuery,
  deviceDetailsMocksSchema,
  interfaceDescription,
  interfaceLabelName,
  interfacesArrayCount,
} from "../../mocks/data/devices";
import { TestProvider } from "../../mocks/jotai/atom";

// URL for the current view
const graphqlQueryItemsUrl = `/objects/InfraDevice/${deviceDetailsMocksId}`;

// Path that will match the route to display the component
const graphqlQueryItemsPath = "/objects/:objectname/:objectid";

// Mock the apollo query and data
const mocks: any[] = [
  // Object details for initial render
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
  // Object details when rendering relationships tab
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
  // Relationships view
  {
    request: {
      query: gql`
        ${deviceDetailsInterfacesMocksQuery}
      `,
    },
    result: {
      data: deviceDetailsInterfacesMocksData,
    },
  },
  {
    request: {
      query: gql`
        ${deviceDetailsInterfacesMocksQuery}
      `,
    },
    result: {
      data: deviceDetailsInterfacesMocksData,
    },
  },
];

// Provide the initial value for jotai
const ObjectDetailsProvider = () => {
  return (
    <TestProvider
      initialValues={[
        [schemaState, deviceDetailsMocksSchema],
        [genericsState, deviceDetailsMocksGenerics],
      ]}>
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
        // Add initial route for the app router, to display the current items view
        routerProps: {
          initialEntries: [graphqlQueryItemsUrl],
        },
      }
    );

    const tabName = `${interfaceLabelName}${deviceDetailsMocksData.InfraDevice.edges[0].node.interfaces.count}`;

    cy.contains(tabName).should("exist");

    cy.contains(tabName).click();

    cy.get("div.flex > .text-sm > :nth-child(3)").should("have.text", interfacesArrayCount);

    cy.contains(interfaceDescription).should("be.visible");
  });
});
