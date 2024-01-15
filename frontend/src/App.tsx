import { addCollection } from "@iconify-icon/react";
import mdiIcons from "@iconify-json/mdi/icons.json";
import { useAtom, useAtomValue } from "jotai";
import * as R from "ramda";
import { useEffect } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { toast } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import { StringParam, useQueryParam } from "use-query-params";
import { ALERT_TYPES, Alert } from "./components/utils/alert";
import { CONFIG } from "./config/config";
import { QSP } from "./config/qsp";
import { MAIN_ROUTES } from "./config/routes";
import { withAuth } from "./decorators/withAuth";
import { Branch } from "./generated/graphql";
import Layout from "./screens/layout/layout";
import { branchesState, currentBranchAtom } from "./state/atoms/branches.atom";
import {
  currentSchemaHashAtom,
  genericsState,
  iGenericSchema,
  iNamespace,
  iNodeSchema,
  namespacesState,
  schemaState,
} from "./state/atoms/schema.atom";
import { schemaKindNameState } from "./state/atoms/schemaKindName.atom";
import "./styles/index.css";
import { findSelectedBranch } from "./utils/branches";
import { sortByName, sortByOrderWeight } from "./utils/common";
import { fetchUrl } from "./utils/fetch";
addCollection(mdiIcons);

function App() {
  const branches = useAtomValue(branchesState);
  const [currentBranch, setCurrentBranch] = useAtom(currentBranchAtom);
  const [currentSchemaHash, setCurrentSchemaHash] = useAtom(currentSchemaHashAtom);
  const [, setSchema] = useAtom(schemaState);
  const [, setSchemaKindNameState] = useAtom(schemaKindNameState);
  const [, setGenerics] = useAtom(genericsState);
  const [, setNamespaces] = useAtom(namespacesState);
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

  useEffect(() => {
    const selectedBranch = findSelectedBranch(branches, branchInQueryString);

    if (selectedBranch?.name === currentBranch?.name) return;
    setCurrentBranch(selectedBranch);

    updateSchemaStateIfNeeded(selectedBranch);
  }, [branches.length, branchInQueryString]);

  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        {MAIN_ROUTES.map((route) => (
          <Route index key={route.path} path={route.path} element={route.element} />
        ))}
        <Route path="*" element={<Navigate to="/" />} />
      </Route>
    </Routes>
  );
}

export default withAuth(App);
