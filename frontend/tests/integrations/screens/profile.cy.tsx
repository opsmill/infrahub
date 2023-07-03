/// <reference types="cypress" />

import { gql } from "@apollo/client";
import { MockedProvider } from "@apollo/client/testing";
import React from "react";
import { ACCESS_TOKEN_KEY } from "../../../src/config/constants";
import { withAuth } from "../../../src/decorators/withAuth";
import Header from "../../../src/screens/layout/header";
import { schemaState } from "../../../src/state/atoms/schema.atom";
import { encodeJwt } from "../../../src/utils/common";
import {
  accountDetailsMocksData,
  accountDetailsMocksQuery,
  accountDetaulsMocksSchema,
  accountId,
} from "../../mocks/data/account";
import { TestProvider } from "../../mocks/jotai/atom";

// Mock the apollo query and data
const mocks: any[] = [
  {
    request: {
      query: gql`
        ${accountDetailsMocksQuery}
      `,
    },
    result: {
      data: accountDetailsMocksData,
    },
  },
];

const AuthHeader = withAuth(Header);

describe("List screen", () => {
  it("should fetch items and render list", () => {
    cy.viewport(1920, 1080);

    const data = {
      sub: accountId,
    };

    const token = encodeJwt(data);

    sessionStorage.setItem(ACCESS_TOKEN_KEY, token);

    // Mount the view with the default route and the mocked data
    cy.mount(
      <MockedProvider mocks={mocks} addTypename={false}>
        <TestProvider initialValues={[[schemaState, accountDetaulsMocksSchema]]}>
          <AuthHeader setSidebarOpen={() => null} />
        </TestProvider>
      </MockedProvider>
    );

    cy.get(".h-12").should("have.text", "A");
  });
});
