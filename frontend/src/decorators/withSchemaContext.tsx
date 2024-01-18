import { useAtom, useAtomValue } from "jotai";
import * as R from "ramda";
import { createContext } from "react";
import { toast } from "react-toastify";
import { StringParam, useQueryParam } from "use-query-params";
import { ALERT_TYPES, Alert } from "../components/utils/alert";
import { CONFIG } from "../config/config";
import { QSP } from "../config/qsp";
import { Branch } from "../generated/graphql";
import { branchesState, currentBranchAtom } from "../state/atoms/branches.atom";
import {
  currentSchemaHashAtom,
  genericsState,
  iGenericSchema,
  iNamespace,
  iNodeSchema,
  namespacesState,
  schemaState,
} from "../state/atoms/schema.atom";
import { schemaKindNameState } from "../state/atoms/schemaKindName.atom";
import { findSelectedBranch } from "../utils/branches";
import { sortByName, sortByOrderWeight } from "../utils/common";
import { fetchUrl } from "../utils/fetch";

type tSchemaContext = {
  checkSchemaUpdate: () => Promise<void>;
};

export const SchemaContext = createContext<tSchemaContext>({
  checkSchemaUpdate: async () => {},
});

export const withSchemaContext = (AppComponent: any) => (props: any) => {
  const [currentBranch, setCurrentBranch] = useAtom(currentBranchAtom);
  const [currentSchemaHash, setCurrentSchemaHash] = useAtom(currentSchemaHashAtom);
  const [, setSchema] = useAtom(schemaState);
  const [, setSchemaKindNameState] = useAtom(schemaKindNameState);
  const [, setGenerics] = useAtom(genericsState);
  const [, setNamespaces] = useAtom(namespacesState);
  const branches = useAtomValue(branchesState);
  const [branchInQueryString] = useQueryParam(QSP.BRANCH, StringParam);

  /**
   * Fetch schema from the backend, and store it
   */
  const fetchAndSetSchema = async (branch: Branch | null) => {
    try {
      const schemaData: {
        main: string;
        nodes: iNodeSchema[];
        generics: iGenericSchema[];
        namespaces: iNamespace[];
      } = await fetchUrl(CONFIG.SCHEMA_URL(branch?.name));

      const hash = schemaData.main;
      const schema = sortByName(schemaData.nodes || []);
      const generics = sortByName(schemaData.generics || []);
      const namespaces = sortByName(schemaData.namespaces || []);

      schema.forEach((s) => {
        s.attributes = sortByOrderWeight(s.attributes || []);
        s.relationships = sortByOrderWeight(s.relationships || []);
      });

      const schemaNames = [...schema.map((s) => s.name), ...generics.map((s) => s.name)];
      const schemaKinds = [...schema.map((s) => s.kind), ...generics.map((s) => s.kind)];
      const schemaKindNameTuples = R.zip(schemaKinds, schemaNames);
      const schemaKindNameMap = R.fromPairs(schemaKindNameTuples);

      setGenerics(generics);
      setCurrentSchemaHash(hash);
      setSchema(schema);
      setSchemaKindNameState(schemaKindNameMap);
      setNamespaces(namespaces);
    } catch (error) {
      toast(
        <Alert type={ALERT_TYPES.ERROR} message="Something went wrong when fetching the schema" />
      );

      console.error("Error while fetching the schema: ", error);
    }
  };

  const updateSchemaStateIfNeeded = async (branch: Branch | null) => {
    try {
      const schemaSummary = await fetchUrl(CONFIG.SCHEMA_SUMMARY_URL(branch?.name));
      const isSameSchema = currentSchemaHash === schemaSummary.main;

      // Updating schema only if it's different from the current one
      if (isSameSchema) return;
      await fetchAndSetSchema(branch);
    } catch (error) {
      console.error("Error while updating the schema state:", error);
    }
  };

  const checkSchemaUpdate = async () => {
    const selectedBranch = findSelectedBranch(branches, branchInQueryString);

    await updateSchemaStateIfNeeded(selectedBranch);

    if (selectedBranch?.name === currentBranch?.name) return;

    setCurrentBranch(selectedBranch);
  };

  const schemaContext = {
    checkSchemaUpdate,
  };

  return (
    <SchemaContext.Provider value={schemaContext}>
      <AppComponent {...props} />
    </SchemaContext.Provider>
  );
};
