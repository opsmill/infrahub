import { MockedProvider } from "@apollo/client/testing";
import { cleanup, render, screen } from "@testing-library/react";
import queryString from "query-string";
import { BrowserRouter } from "react-router-dom";
import { QueryParamProvider } from "use-query-params";
import { ReactRouter6Adapter } from "use-query-params/adapters/react-router-6";
import { afterAll, describe, expect, it } from "vitest";
import { branchesMocks } from "../../mocks/data/branches";
import Apollo, { QUERY } from "./branch-list";

afterAll(cleanup);

const mocks: any[] = [
  {
    request: {
      query: QUERY,
      variables: { offset: 0, limit: 10 },
    },
    result: {
      data: {
        Branch: branchesMocks,
      },
    },
  },
];

describe("Branch list", () => {
  it("should query the branch list and display the result", async () => {
    render(
      <BrowserRouter basename="/">
        <QueryParamProvider
          adapter={ReactRouter6Adapter}
          options={{
            searchStringToObject: queryString.parse,
            objectToSearchString: queryString.stringify,
          }}>
          <MockedProvider mocks={mocks} addTypename={false}>
            <Apollo />
          </MockedProvider>
        </QueryParamProvider>
      </BrowserRouter>
    );

    expect(await screen.findByText("Loading...")).toBeTruthy();

    expect(await screen.findByText("Working!")).toBeTruthy();
  });
});
