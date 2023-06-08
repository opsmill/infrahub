import { Provider } from "jotai";
import { useHydrateAtoms } from "jotai/utils";

export const HydrateAtoms = ({ initialValues, children }: any) => {
  useHydrateAtoms(initialValues);
  return children;
};

export const TestProvider = ({ initialValues, children }: any) => (
  <Provider>
    <HydrateAtoms initialValues={initialValues}>{children}</HydrateAtoms>
  </Provider>
);
