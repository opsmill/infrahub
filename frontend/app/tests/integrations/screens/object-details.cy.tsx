/// <reference types="cypress" />

import { gql } from "@apollo/client";
import { MockedProvider } from "@apollo/client/testing";
import { ErrorBoundary } from "react-error-boundary";
import { Route, Routes } from "react-router";
import { BranchContext } from "../../../src/entities/branches/ui/branches-provider";
import { ObjectDetailsPage } from "../../../src/pages/objects/object-details";
import ErrorFallback from "../../../src/shared/components/errors/error-fallback";
import { generateBranch } from "../../fake/branch";
import {
  deviceDetailsMocksASNName,
  deviceDetailsMocksData,
  deviceDetailsMocksId,
  deviceDetailsMocksOwnerName,
  deviceDetailsMocksQuery,
  deviceDetailsMocksSchema,
  deviceDetailsMocksTagName,
  getPermissionsData,
  getPermissionsQuery,
} from "../../mocks/data/devices";

// URL for the current view
const graphqlQueryItemsUrl = `/objects/InfraDevice/${deviceDetailsMocksId}`;

// Path that will match the route to display the component
const graphqlQueryItemsPath = "/objects/:objectKind/:objectid";

// Mock the apollo query and data
const mocks: any[] = [
  {
    request: {
      query: gql`
        ${deviceDetailsMocksQuery}
      `,
      variables: { offset: 0, limit: 10 },
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
      variables: { offset: 0, limit: 10 },
    },
    result: {
      data: deviceDetailsMocksData,
    },
  },
  // Permissions
  {
    request: {
      query: gql`
        ${getPermissionsQuery}
      `,
      variables: { offset: 0, limit: 10 },
    },
    result: {
      data: getPermissionsData,
    },
  },
];

describe("List screen", () => {
  it("should fetch object details and render a list of details", () => {
    cy.viewport(1920, 1080);
    cy.fixture("config").then(function (json) {
      cy.intercept("GET", "/api/config", json).as("config");
    });

    // Mount the view with the default route and the mocked data
    cy.mount(
      <BranchContext value={{ currentBranch: generateBranch(), setCurrentBranch: () => {} }}>
        <MockedProvider mocks={mocks} addTypename={false}>
          <ErrorBoundary FallbackComponent={ErrorFallback}>
            <Routes>
              <Route
                element={<ObjectDetailsPage schema={deviceDetailsMocksSchema[0]} />}
                path={graphqlQueryItemsPath}
              />
            </Routes>
          </ErrorBoundary>
        </MockedProvider>
      </BranchContext>,
      {
        // Add iniital route for the app router, to display the current items view
        routerProps: {
          initialEntries: [graphqlQueryItemsUrl],
        },
      }
    );

    // The device ASN should be correctly named
    cy.contains("Asn").siblings().first().should("have.text", deviceDetailsMocksASNName);

    cy.contains("Asn")
      .siblings()
      .first()
      .within(() => {
        cy.get("[data-cy='metadata-button']").click();
      });

    cy.get("[data-cy='metadata-tooltip']").should("contain.text", deviceDetailsMocksOwnerName);

    cy.contains("Tags")
      .parent()
      .within(() => {
        cy.contains(deviceDetailsMocksTagName).should("be.visible");
      });
  });
});
