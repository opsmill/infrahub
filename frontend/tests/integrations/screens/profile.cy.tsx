/// <reference types="cypress" />

import { gql } from "@apollo/client";
import { MockedProvider } from "@apollo/client/testing";
import React from "react";
import { initials } from "../../../src/components/display/avatar";
import { ACCESS_TOKEN_KEY } from "../../../src/config/constants";
import { schemaState } from "../../../src/state/atoms/schema.atom";
import { encodeJwt } from "../../../src/utils/common";
import { accountDetailsMocksSchema } from "../../mocks/data/account";
import {
  profileDetailsMocksData,
  profileDetailsMocksQuery,
  profileId,
} from "../../mocks/data/profile";
import { TestProvider } from "../../mocks/jotai/atom";
import { AuthProvider } from "../../../src/hooks/useAuth";
import Header from "../../../src/screens/layout/header";

// Mock the apollo query and data
const mocks: any[] = [
  {
    request: {
      query: gql`
        ${profileDetailsMocksQuery}
      `,
    },
    result: {
      data: profileDetailsMocksData,
    },
  },
];

const AuthHeader = () => (
  <AuthProvider>
    <Header />
  </AuthProvider>
);

describe("List screen", () => {
  it("should fetch items and render list", () => {
    cy.viewport(1920, 1080);

    const data = {
      sub: profileId,
    };

    const token = encodeJwt(data);

    localStorage.setItem(ACCESS_TOKEN_KEY, token);

    // Mount the view with the default route and the mocked data
    cy.mount(
      <MockedProvider mocks={mocks} addTypename={false}>
        <TestProvider initialValues={[[schemaState, accountDetailsMocksSchema]]}>
          <AuthHeader setSidebarOpen={() => null} />
        </TestProvider>
      </MockedProvider>
    );

    cy.get(".h-12").should(
      "have.text",
      initials(profileDetailsMocksData.AccountProfile.display_label)
    );
  });
});
