import { render, screen } from "@testing-library/react";
import { Provider } from "jotai";
import { useHydrateAtoms } from "jotai/utils";
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

test("should not increment on max (100)", () => {
  render(<ObjectItemDetailsProvider />);

  const query = screen.getByText(/Query:.*/);
  console.log("query: ", query);
});
