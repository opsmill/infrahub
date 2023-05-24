import { render, screen } from "@testing-library/react";
import { Provider } from "jotai";
import { useHydrateAtoms } from "jotai/utils";
import React from "react";
import { describe, it } from "vitest";
import { schemaMocks } from "../../../mocks/schema";
import ObjectItemDetails from "../../components/tests/object-item-details";
import { schemaState } from "../../state/atoms/schema.atom";

const HydrateAtoms = ({ initialValues, children }: any) => {
  useHydrateAtoms(initialValues);
  return children;
};

const TestProvider = ({ initialValues, children }: any) => (
  <Provider>
    <HydrateAtoms initialValues={initialValues}>{children}</HydrateAtoms>
  </Provider>
);

const ObjectItemDetailsProvider = () => {
  return (
    <TestProvider initialValues={[[schemaState, schemaMocks]]}>
      <ObjectItemDetails />
    </TestProvider>
  );
};

describe("Object item details", () => {
  it("should compute a correct query", () => {
    render(<ObjectItemDetailsProvider />);

    const query = screen.getByText(/Query:.*/);
    console.log("query: ", query);
  });
});
