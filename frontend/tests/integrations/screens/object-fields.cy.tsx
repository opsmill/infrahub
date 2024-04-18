/// <reference types="cypress" />

import { MockedProvider } from "@apollo/client/testing";
import React from "react";
import { Route, Routes } from "react-router-dom";
import { schemaState } from "../../../src/state/atoms/schema.atom";

import { gql } from "@apollo/client";
import { ACCESS_TOKEN_KEY } from "../../../src/config/constants";
import { AuthProvider } from "../../../src/hooks/useAuth";
import ObjectItems from "../../../src/screens/object-items/object-items-paginated";
import { encodeJwt } from "../../../src/utils/common";
import { accountDetailsMocksSchema } from "../../mocks/data/account";
import {
  profileDetailsMocksData,
  profileDetailsMocksQuery,
  profileId,
} from "../../mocks/data/account-profile";
import {
  taskMocksData as taskMocksData1,
  taskMocksQuery as taskMocksQuery1,
  taskMocksSchema as taskMocksSchema1,
  taskMocksSchemaOptional as taskMocksSchemaOptionnal1,
} from "../../mocks/data/task_1";
import {
  taskMocksData as taskMocksData2,
  taskMocksQuery as taskMocksQuery2,
  taskMocksSchema as taskMocksSchema2,
  taskMocksSchemaOptional as taskMocksSchemaOptional2,
  taskMocksSchemaWithDefaultValue as taskMocksSchemaWithDefaultValue2,
} from "../../mocks/data/task_2";
import {
  taskMocksData as taskMocksData3,
  taskMocksQuery as taskMocksQuery3,
  taskMocksSchema as taskMocksSchema3,
  taskMocksSchemaOptional as taskMocksSchemaOptional3,
  taskMocksSchemaWithDefaultValue as taskMocksSchemaWithDefaultValue3,
} from "../../mocks/data/task_3";
import {
  taskMocksData as taskMocksData4,
  taskMocksQuery as taskMocksQuery4,
  taskMocksSchema as taskMocksSchema4,
} from "../../mocks/data/task_4";
import { TestProvider } from "../../mocks/jotai/atom";

// URL for the current view
const mockedUrl = "/objects/TestTask";

// Path that will match the route to display the component
const mockedPath = "/objects/:objectname";

// Mock the apollo query and data
const mocks: any[] = [
  {
    request: {
      query: gql`
        ${profileDetailsMocksQuery}
      `,
      variables: { offset: 0, limit: 10 },
    },
    result: {
      data: profileDetailsMocksData,
    },
  },
  {
    request: {
      query: gql`
        ${taskMocksQuery1}
      `,
      variables: { offset: 0, limit: 10 },
    },
    result: {
      data: taskMocksData1,
    },
  },
  {
    request: {
      query: gql`
        ${taskMocksQuery2}
      `,
      variables: { offset: 0, limit: 10 },
    },
    result: {
      data: taskMocksData2,
    },
  },
  {
    request: {
      query: gql`
        ${taskMocksQuery3}
      `,
      variables: { offset: 0, limit: 10 },
    },
    result: {
      data: taskMocksData3,
    },
  },
  {
    request: {
      query: gql`
        ${taskMocksQuery4}
      `,
      variables: { offset: 0, limit: 10 },
    },
    result: {
      data: taskMocksData4,
    },
  },
];

const AuthenticatedObjectItems = () => (
  <AuthProvider>
    <ObjectItems />
  </AuthProvider>
);

describe("Object list", () => {
  beforeEach(function () {
    const data = {
      sub: profileId,
      user_claims: {
        role: "admin",
      },
    };

    const token = encodeJwt(data);

    localStorage.setItem(ACCESS_TOKEN_KEY, token);
  });

  it("should open the add panel, submit without filling the text field and display a required message", function () {
    cy.viewport(1920, 1080);

    cy.intercept("POST", "/graphql/main ", this.mutation).as("mutate");

    // Provide the initial value for jotai
    const ObjectItemsProvider = () => {
      return (
        <TestProvider
          initialValues={[[schemaState, [...accountDetailsMocksSchema, ...taskMocksSchema1]]]}>
          <AuthenticatedObjectItems />
        </TestProvider>
      );
    };

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

    // Open edit panel
    cy.get("[data-cy='create']").click();

    // Save
    cy.get(".bg-custom-blue-700").click();

    // The required message should appear
    cy.get("[data-cy='field-error-message']").should("have.text", "Required");
  });

  it("should open the add panel, submit after filling the text field and do not display a required message", function () {
    cy.viewport(1920, 1080);

    cy.intercept("POST", "/graphql/main ", this.mutation).as("mutate");

    // Provide the initial value for jotai
    const ObjectItemsProvider = () => {
      return (
        <TestProvider
          initialValues={[
            [schemaState, [...accountDetailsMocksSchema, ...taskMocksSchemaOptionnal1]],
          ]}>
          <AuthenticatedObjectItems />
        </TestProvider>
      );
    };

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

    // Open edit panel
    cy.get("[data-cy='create']").click();

    // Save
    cy.get(".bg-custom-blue-700").click();

    // The required message should appear
    cy.get("[data-cy='field-error-message']").should("not.exist");
  });

  it("should open the add panel, submit without checking the checkbox and display a required message", function () {
    cy.viewport(1920, 1080);

    cy.intercept("POST", "/graphql/main ", this.mutation).as("mutate");

    // Provide the initial value for jotai
    const ObjectItemsProvider = () => {
      return (
        <TestProvider
          initialValues={[[schemaState, [...accountDetailsMocksSchema, ...taskMocksSchema2]]]}>
          <AuthenticatedObjectItems />
        </TestProvider>
      );
    };

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

    // Open edit panel
    cy.get("[data-cy='create']").click();

    // Save
    cy.get(".bg-custom-blue-700").click();

    // The required message should appear
    cy.get("[data-cy='field-error-message']").should("have.text", "Required");
  });

  it("should open the add panel, submit without checking the checkbox and should not display a required message (default value is defined)", function () {
    cy.viewport(1920, 1080);

    cy.intercept("POST", "/graphql/main ", this.mutation).as("mutate");

    // Provide the initial value for jotai
    const ObjectItemsProvider = () => {
      return (
        <TestProvider
          initialValues={[
            [schemaState, [...accountDetailsMocksSchema, ...taskMocksSchemaWithDefaultValue2]],
          ]}>
          <AuthenticatedObjectItems />
        </TestProvider>
      );
    };

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

    // Open edit panel
    cy.get("[data-cy='create']").click();

    // Save
    cy.get(".bg-custom-blue-700").click();

    // The required message should appear
    cy.get("[data-cy='field-error-message']").should("not.exist");
  });

  it("should open the add panel, submit without checking the checkbox and should not display a required message (optional)", function () {
    cy.viewport(1920, 1080);

    cy.intercept("POST", "/graphql/main ", this.mutation).as("mutate");

    // Provide the initial value for jotai
    const ObjectItemsProvider = () => {
      return (
        <TestProvider
          initialValues={[
            [schemaState, [...accountDetailsMocksSchema, ...taskMocksSchemaOptional2]],
          ]}>
          <AuthenticatedObjectItems />
        </TestProvider>
      );
    };

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

    // Open edit panel
    cy.get("[data-cy='create']").click();

    // Save
    cy.get(".bg-custom-blue-700").click();

    // The required message should appear
    cy.get("[data-cy='field-error-message']").should("not.exist");
  });

  it("should open the add panel, submit without defining an integer and display a required message", function () {
    cy.viewport(1920, 1080);

    cy.intercept("POST", "/graphql/main ", this.mutation).as("mutate");

    // Provide the initial value for jotai
    const ObjectItemsProvider = () => {
      return (
        <TestProvider
          initialValues={[[schemaState, [...accountDetailsMocksSchema, ...taskMocksSchema3]]]}>
          <AuthenticatedObjectItems />
        </TestProvider>
      );
    };

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

    // Open edit panel
    cy.get("[data-cy='create']").click();

    // Save
    cy.get(".bg-custom-blue-700").click();

    // The required message should appear
    cy.get("[data-cy='field-error-message']").should("have.text", "Required");
  });

  it("should open the add panel, submit without defining an integer and should not display a required message (0 should work as defined integer)", function () {
    cy.viewport(1920, 1080);

    cy.intercept("POST", "/graphql/main ", this.mutation).as("mutate");

    // Provide the initial value for jotai
    const ObjectItemsProvider = () => {
      return (
        <TestProvider
          initialValues={[[schemaState, [...accountDetailsMocksSchema, ...taskMocksSchema3]]]}>
          <AuthenticatedObjectItems />
        </TestProvider>
      );
    };

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

    // Open edit panel
    cy.get("[data-cy='create']").click();

    // Type 0 as value
    cy.get("#Counter").type("0", { delay: 0, force: true });

    // Save
    cy.get(".bg-custom-blue-700").click();

    // The required message should not appear
    cy.get("[data-cy='field-error-message']").should("not.exist");
  });

  it("should open the add panel, submit without defining an integer and should not display a required message (default value is defined)", function () {
    cy.viewport(1920, 1080);

    cy.intercept("POST", "/graphql/main ", this.mutation).as("mutate");

    // Provide the initial value for jotai
    const ObjectItemsProvider = () => {
      return (
        <TestProvider
          initialValues={[
            [schemaState, [...accountDetailsMocksSchema, ...taskMocksSchemaWithDefaultValue3]],
          ]}>
          <AuthenticatedObjectItems />
        </TestProvider>
      );
    };

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

    // Open edit panel
    cy.get("[data-cy='create']").click();

    // Save
    cy.get(".bg-custom-blue-700").click();

    // The required message should not appear
    cy.get("[data-cy='field-error-message']").should("not.exist");
  });

  it("should open the add panel, submit without defining an integer and should not display a required message (optional)", function () {
    cy.viewport(1920, 1080);

    cy.intercept("POST", "/graphql/main ", this.mutation).as("mutate");

    // Provide the initial value for jotai
    const ObjectItemsProvider = () => {
      return (
        <TestProvider
          initialValues={[
            [schemaState, [...accountDetailsMocksSchema, ...taskMocksSchemaOptional3]],
          ]}>
          <AuthenticatedObjectItems />
        </TestProvider>
      );
    };

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

    // Open edit panel
    cy.get("[data-cy='create']").click();

    // Save
    cy.get(".bg-custom-blue-700").click();

    // The required message should not appear
    cy.get("[data-cy='field-error-message']").should("not.exist");
  });

  it("should open the add panel, submit without defining a datetime and should display a required message", function () {
    cy.viewport(1920, 1080);

    cy.intercept("POST", "/graphql/main ", this.mutation).as("mutate");

    // Provide the initial value for jotai
    const ObjectItemsProvider = () => {
      return (
        <TestProvider
          initialValues={[[schemaState, [...accountDetailsMocksSchema, ...taskMocksSchema4]]]}>
          <AuthenticatedObjectItems />
        </TestProvider>
      );
    };

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

    // Open edit panel
    cy.get("[data-cy='create']").click();

    // Save
    cy.get(".bg-custom-blue-700").click();

    // The required message should appear
    cy.get("[data-cy='field-error-message']").should("have.text", "Required");
  });
});
