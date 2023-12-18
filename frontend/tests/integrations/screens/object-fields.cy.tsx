/// <reference types="cypress" />

import { MockedProvider } from "@apollo/client/testing";
import React from "react";
import { Route, Routes } from "react-router-dom";
import { withAuth } from "../../../src/decorators/withAuth";
import { schemaFamily } from "../../../src/state/atoms/schema.atom";

import { gql } from "@apollo/client";
import { ACCESS_TOKEN_KEY } from "../../../src/config/constants";
import ObjectItems from "../../../src/screens/object-items/object-items-paginated";
import { encodeJwt } from "../../../src/utils/common";
import { accountDetailsMocksSchema } from "../../mocks/data/account";
import {
  profileDetailsMocksData,
  profileDetailsMocksQuery,
  profileId,
} from "../../mocks/data/profile";
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
    },
    result: {
      data: taskMocksData4,
    },
  },
];

const AuthenticatedObjectItems = withAuth(ObjectItems);

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

  afterEach(() => {
    schemaFamily.setShouldRemove(() => true); // set function to remove all
    schemaFamily.setShouldRemove(null); // clear function
  });

  it("should open the add panel, submit without filling the text field and display a required message", function () {
    cy.viewport(1920, 1080);

    cy.intercept("POST", "/graphql/main ", this.mutation).as("mutate");

    // Provide the initial value for jotai
    [...accountDetailsMocksSchema, ...taskMocksSchema1].forEach((s) => {
      schemaFamily(s);
    });

    // Mount the view with the default route and the mocked data
    cy.mount(
      <MockedProvider mocks={mocks} addTypename={false}>
        <Routes>
          <Route element={<AuthenticatedObjectItems />} path={mockedPath} />
        </Routes>
      </MockedProvider>,
      {
        // Add initial route for the app router, to display the current items view
        routerProps: {
          initialEntries: [mockedUrl],
        },
      }
    );

    // Open edit panel
    cy.get(".p-2").click();

    // Save
    cy.get(".bg-custom-blue-700").click();

    // The required message should appear
    cy.get("[data-cy='field-error-message']").should("have.text", "Required");
  });

  it("should open the add panel, submit after filling the text field and do not display a required message", function () {
    cy.viewport(1920, 1080);

    cy.intercept("POST", "/graphql/main ", this.mutation).as("mutate");

    // Provide the initial value for jotai
    [...accountDetailsMocksSchema, ...taskMocksSchemaOptionnal1].forEach((s) => {
      schemaFamily(s);
    });

    // Mount the view with the default route and the mocked data
    cy.mount(
      <MockedProvider mocks={mocks} addTypename={false}>
        <Routes>
          <Route element={<AuthenticatedObjectItems />} path={mockedPath} />
        </Routes>
      </MockedProvider>,
      {
        // Add initial route for the app router, to display the current items view
        routerProps: {
          initialEntries: [mockedUrl],
        },
      }
    );

    // Open edit panel
    cy.get(".p-2").click();

    // Save
    cy.get(".bg-custom-blue-700").click();

    // The required message should appear
    cy.get("[data-cy='field-error-message']").should("not.exist");
  });

  it("should open the add panel, submit without checking the checkbox and display a required message", function () {
    cy.viewport(1920, 1080);

    cy.intercept("POST", "/graphql/main ", this.mutation).as("mutate");

    // Provide the initial value for jotai
    [...accountDetailsMocksSchema, ...taskMocksSchema2].forEach((s) => {
      schemaFamily(s);
    });

    // Mount the view with the default route and the mocked data
    cy.mount(
      <MockedProvider mocks={mocks} addTypename={false}>
        <Routes>
          <Route element={<AuthenticatedObjectItems />} path={mockedPath} />
        </Routes>
      </MockedProvider>,
      {
        // Add initial route for the app router, to display the current items view
        routerProps: {
          initialEntries: [mockedUrl],
        },
      }
    );

    // Open edit panel
    cy.get(".p-2").click();

    // Save
    cy.get(".bg-custom-blue-700").click();

    // The required message should appear
    cy.get("[data-cy='field-error-message']").should("have.text", "Required");
  });

  it("should open the add panel, submit without checking the checkbox and should not display a required message (default value is defined)", function () {
    cy.viewport(1920, 1080);

    cy.intercept("POST", "/graphql/main ", this.mutation).as("mutate");

    // Provide the initial value for jotai
    [...accountDetailsMocksSchema, ...taskMocksSchemaWithDefaultValue2].forEach((s) => {
      schemaFamily(s);
    });

    // Mount the view with the default route and the mocked data
    cy.mount(
      <MockedProvider mocks={mocks} addTypename={false}>
        <Routes>
          <Route element={<AuthenticatedObjectItems />} path={mockedPath} />
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
    cy.get(".p-2").click();

    // Save
    cy.get(".bg-custom-blue-700").click();

    // The required message should appear
    cy.get("[data-cy='field-error-message']").should("not.exist");
  });

  it("should open the add panel, submit without checking the checkbox and should not display a required message (optional)", function () {
    cy.viewport(1920, 1080);

    cy.intercept("POST", "/graphql/main ", this.mutation).as("mutate");

    // Provide the initial value for jotai
    [...accountDetailsMocksSchema, ...taskMocksSchemaOptional2].forEach((s) => {
      schemaFamily(s);
    });

    // Mount the view with the default route and the mocked data
    cy.mount(
      <MockedProvider mocks={mocks} addTypename={false}>
        <Routes>
          <Route element={<AuthenticatedObjectItems />} path={mockedPath} />
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
    cy.get(".p-2").click();

    // Save
    cy.get(".bg-custom-blue-700").click();

    // The required message should appear
    cy.get("[data-cy='field-error-message']").should("not.exist");
  });

  it("should open the add panel, submit without defining an integer and display a required message", function () {
    cy.viewport(1920, 1080);

    cy.intercept("POST", "/graphql/main ", this.mutation).as("mutate");

    // Provide the initial value for jotai
    [...accountDetailsMocksSchema, ...taskMocksSchema3].forEach((s) => {
      schemaFamily(s);
    });

    // Mount the view with the default route and the mocked data
    cy.mount(
      <MockedProvider mocks={mocks} addTypename={false}>
        <Routes>
          <Route element={<AuthenticatedObjectItems />} path={mockedPath} />
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
    cy.get(".p-2").click();

    // Save
    cy.get(".bg-custom-blue-700").click();

    // The required message should appear
    cy.get("[data-cy='field-error-message']").should("have.text", "Required");
  });

  it("should open the add panel, submit without defining an integer and should not display a required message (0 should work as defined integer)", function () {
    cy.viewport(1920, 1080);

    cy.intercept("POST", "/graphql/main ", this.mutation).as("mutate");

    // Provide the initial value for jotai
    [...accountDetailsMocksSchema, ...taskMocksSchema3].forEach((s) => {
      schemaFamily(s);
    });

    // Mount the view with the default route and the mocked data
    cy.mount(
      <MockedProvider mocks={mocks} addTypename={false}>
        <Routes>
          <Route element={<AuthenticatedObjectItems />} path={mockedPath} />
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
    cy.get(".p-2").click();

    // Type 0 as value
    cy.get(".sm\\:col-span-7 > .relative > .block").type("0", { delay: 0, force: true });

    // Save
    cy.get(".bg-custom-blue-700").click();

    // The required message should not appear
    cy.get("[data-cy='field-error-message']").should("not.exist");
  });

  it("should open the add panel, submit without defining an integer and should not display a required message (default value is defined)", function () {
    cy.viewport(1920, 1080);

    cy.intercept("POST", "/graphql/main ", this.mutation).as("mutate");

    // Provide the initial value for jotai
    [...accountDetailsMocksSchema, ...taskMocksSchemaWithDefaultValue3].forEach((s) => {
      schemaFamily(s);
    });

    // Mount the view with the default route and the mocked data
    cy.mount(
      <MockedProvider mocks={mocks} addTypename={false}>
        <Routes>
          <Route element={<AuthenticatedObjectItems />} path={mockedPath} />
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
    cy.get(".p-2").click();

    // Save
    cy.get(".bg-custom-blue-700").click();

    // The required message should not appear
    cy.get("[data-cy='field-error-message']").should("not.exist");
  });

  it("should open the add panel, submit without defining an integer and should not display a required message (optional)", function () {
    cy.viewport(1920, 1080);

    cy.intercept("POST", "/graphql/main ", this.mutation).as("mutate");

    // Provide the initial value for jotai
    [...accountDetailsMocksSchema, ...taskMocksSchemaOptional3].forEach((s) => {
      schemaFamily(s);
    });

    // Mount the view with the default route and the mocked data
    cy.mount(
      <MockedProvider mocks={mocks} addTypename={false}>
        <Routes>
          <Route element={<AuthenticatedObjectItems />} path={mockedPath} />
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
    cy.get(".p-2").click();

    // Save
    cy.get(".bg-custom-blue-700").click();

    // The required message should not appear
    cy.get("[data-cy='field-error-message']").should("not.exist");
  });

  it("should open the add panel, submit without defining a datetime and should display a required message", function () {
    cy.viewport(1920, 1080);

    cy.intercept("POST", "/graphql/main ", this.mutation).as("mutate");

    // Provide the initial value for jotai
    [...accountDetailsMocksSchema, ...taskMocksSchema4].forEach((s) => {
      schemaFamily(s);
    });

    // Mount the view with the default route and the mocked data
    cy.mount(
      <MockedProvider mocks={mocks} addTypename={false}>
        <Routes>
          <Route element={<AuthenticatedObjectItems />} path={mockedPath} />
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
    cy.get(".p-2").click();

    // Save
    cy.get(".bg-custom-blue-700").click();

    // The required message should appear
    cy.get("[data-cy='field-error-message']").should("have.text", "Required");
  });
});
