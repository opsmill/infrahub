import { MockedProvider } from "@apollo/client/testing";
import { cleanup, render, screen } from "@testing-library/react";
import Apollo, { QUERY } from "../../components/tests/branch-list-test";

afterAll(cleanup);

const branch1 = {
  id: "123",
  name: "test-branch",
  description: "Test branch",
  origin_branch: "main",
  branched_from: "main",
  created_at: 123,
  branched_at: 123,
  is_data_only: true,
};

const mocks: any[] = [
  {
    request: {
      query: QUERY,
    },
    result: {
      data: {
        branch: [branch1],
      },
    },
  },
];

describe("Branch list", () => {
  it("should query the branch list and display the result", async () => {
    render(
      <MockedProvider mocks={mocks} addTypename={false}>
        <Apollo />
      </MockedProvider>
    );

    expect(await screen.findByText("Loading...")).toBeTruthy();

    expect(await screen.findByText("Working!")).toBeTruthy();
  });
});
