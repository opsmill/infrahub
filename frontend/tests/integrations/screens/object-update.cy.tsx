/// <reference types="cypress" />

import { gql } from "@apollo/client";
import { MockedProvider } from "@apollo/client/testing";
import { formatDistanceToNow } from "date-fns";
import React from "react";
import { Route, Routes } from "react-router-dom";
import { ACCESS_TOKEN_KEY } from "../../../src/config/constants";
import { withAuth } from "../../../src/decorators/withAuth";
import ObjectDetails from "../../../src/screens/object-item-details/object-item-details-paginated";
import { configState } from "../../../src/state/atoms/config.atom";
import { schemaFamily, schemaState } from "../../../src/state/atoms/schema.atom";
import { mockedToken } from "../../fixtures/auth";
import {
  accountTokenDetailsMocksDataBis,
  accountTokenDetailsMocksDataWithDateBis,
  accountTokenDetailsMocksQueryBis,
  accountTokenDetailsMocksSchemaBIS,
  accountTokenEditMocksDataBis,
  accountTokenEditMocksQueryBis,
  accountTokenId,
  accountTokenNewDate,
} from "../../mocks/data/accountToken";
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
const mockedUrl = `/objects/InfraDevice/${deviceDetailsMocksId}`;
const mockedUrlToken = `/objects/InternalAccountTokenBis/${accountTokenId}`;

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

const mocksToken = [
  // Account token details
  {
    request: {
      query: gql`
        ${accountTokenDetailsMocksQueryBis}
      `,
    },
    result: {
      data: accountTokenDetailsMocksDataBis,
    },
  },
  // Account token details for edit panel
  {
    request: {
      query: gql`
        ${accountTokenEditMocksQueryBis}
      `,
    },
    result: {
      data: accountTokenEditMocksDataBis,
    },
  },
  // Account token details after update
  {
    request: {
      query: gql`
        ${accountTokenDetailsMocksQueryBis}
      `,
    },
    result: {
      data: accountTokenDetailsMocksDataWithDateBis,
    },
  },
];

const AuthenticatedObjectItems = withAuth(ObjectDetails);

// Provide the initial value for jotai
[...deviceDetailsMocksSchema, ...accountTokenDetailsMocksSchemaBIS].forEach((s) => {
  schemaFamily(s);
});
const ObjectDetailsProvider = () => {
  return (
    <TestProvider
      initialValues={[
        [schemaState, [...deviceDetailsMocksSchema, ...accountTokenDetailsMocksSchemaBIS]],
        [configState, configMocks],
      ]}>
      <AuthenticatedObjectItems />
    </TestProvider>
  );
};

describe("Object details", () => {
  beforeEach(function () {
    cy.fixture("device-detail-update-name").as("mutation");
    cy.fixture("account-token-update-date").as("mutationToken");
    localStorage.setItem(ACCESS_TOKEN_KEY, mockedToken);
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
    cy.get(".grid > :nth-child(1) > .relative > .block").type(deviceDetailsNewName, {
      delay: 0,
      force: true,
    });

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

  it("should fetch the object details, open the edit form and update the account token date", function () {
    cy.viewport(1920, 1080);

    cy.intercept("POST", "/graphql/main ", this.mutationToken).as("mutate");

    // Mount the view with the default route and the mocked data
    cy.mount(
      <MockedProvider mocks={mocksToken} addTypename={false}>
        <Routes>
          <Route element={<ObjectDetailsProvider />} path={mockedPath} />
        </Routes>
      </MockedProvider>,
      {
        // Add iniital route for the app router, to display the current items view
        routerProps: {
          initialEntries: [mockedUrlToken],
        },
      }
    );

    // Open edit panel
    cy.get(".flex-col > .bg-custom-white > :nth-child(2) > :nth-child(1)").click();

    // Date input should be empty
    cy.get(".react-datepicker__input-container > .relative > .block").should("have.text", "");

    // Select a date
    cy.get(".react-datepicker__input-container > .relative > .block").click();
    cy.get(".react-datepicker__day--013").click(); // Date number 13
    cy.get(".react-datepicker__input-container > .relative > .block").should("include.value", "13");

    // Select an account
    cy.get("[id^=headlessui-combobox-button-]").click();
    cy.get("[id^=headlessui-combobox-option-]").eq(1).click(); // Get second option (first = empty)

    // Verify that the button is not in a loading state
    cy.get(".bg-custom-blue-700").should("have.text", "Save");

    // Submit the form
    cy.get(".bg-custom-blue-700").click();

    // Wait for the mutation to be done
    cy.wait("@mutate");

    // The date should be defined
    cy.get(".text-xs").should(
      "have.text",
      formatDistanceToNow(new Date(accountTokenNewDate), { addSuffix: true })
    );
  });
});
