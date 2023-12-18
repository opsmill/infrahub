import { addCollection } from "@iconify-icon/react";
import mdiIcons from "@iconify-json/mdi/icons.json";
import { useAtom, useAtomValue, useSetAtom } from "jotai";
import * as R from "ramda";
import { useEffect } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { toast } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import { StringParam, useQueryParam } from "use-query-params";
import { ALERT_TYPES, Alert } from "./components/alert";
import { CONFIG } from "./config/config";
import { QSP } from "./config/qsp";
import { MAIN_ROUTES } from "./config/routes";
import { withAuth } from "./decorators/withAuth";
import { Branch } from "./generated/graphql";
import Layout from "./screens/layout/layout";
import { branchesState, currentBranchAtom } from "./state/atoms/branches.atom";
import {
  schemaSummaryAtom,
  genericsState,
  iGenericSchema,
  iNamespace,
  iNodeSchema,
  namespacesState,
  schemaState,
  SchemaSummary,
  schemaFamily,
} from "./state/atoms/schema.atom";
import { schemaKindNameState } from "./state/atoms/schemaKindName.atom";
import "./styles/index.css";
import { sortByOrderWeight } from "./utils/common";
import { fetchUrl } from "./utils/fetch";
addCollection(mdiIcons);

const sortByName = R.sortBy(R.compose(R.toLower, R.prop("name")));

function App() {
  const branches = useAtomValue(branchesState);
  const setCurrentBranch = useSetAtom(currentBranchAtom);
  const [currentSchemaHash, setCurrentSchemaHash] = useAtom(currentSchemaHashAtom);
  const [, setSchema] = useAtom(schemaState);
  const [, setSchemaKindNameState] = useAtom(schemaKindNameState);
  const [currentSchemaHash, setCurrentSchemaHash] = useAtom(schemaSummaryAtom);
  const [, setGenerics] = useAtom(genericsState);
  const [, setNamespaces] = useAtom(namespacesState);
  const [branchInQueryString] = useQueryParam(QSP.BRANCH, StringParam);

  /**
   * Fetch schema from the backend, and store it
   */
  const fetchAndSetSchema = async () => {
    try {
      const schemaData: {
        main: string;
        nodes: iNodeSchema[];
        generics: iGenericSchema[];
        namespaces: iNamespace[];
      } = await fetchUrl(CONFIG.SCHEMA_URL(branchInQueryString));

      const schema = sortByName(schemaData.nodes || []);
      const generics = sortByName(schemaData.generics || []);
      const namespaces = sortByName(schemaData.namespaces || []);

      schema.forEach((s) => {
        s.attributes = sortByOrderWeight(s.attributes || []);
        s.relationships = sortByOrderWeight(s.relationships || []);
        schemaFamily(s);
      });

      generics.forEach((g) => {
        schemaFamily(g);
      });

      const schemaNames = schema.map((s) => s.name);
      const schemaKinds = schema.map((s) => s.kind);
      const schemaKindNameTuples = R.zip(schemaKinds, schemaNames);
      const schemaKindNameMap = R.fromPairs(schemaKindNameTuples);

      setGenerics(generics);
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

  const fetchAndSetSchemaSummary = async () => {
    try {
      const schemaSummary: SchemaSummary = await fetchUrl(
        CONFIG.SCHEMA_SUMMARY_URL(branchInQueryString)
      );

      setCurrentSchemaHash(schemaSummary);
    } catch (error) {
      toast(
        <Alert
          type={ALERT_TYPES.ERROR}
          message="Something went wrong when fetching the schema summary"
        />
      );

      console.error("Error while fetching the schema summary: ", error);
    }
  };

  useEffect(() => {
    fetchAndSetSchema();
    fetchAndSetSchemaSummary();
  }, []);

  const updateSchemaStateIfNeeded = async () => {
    if (!currentSchemaHash) return;

    try {
      const newSchemaSummary: SchemaSummary = await fetchUrl(
        CONFIG.SCHEMA_SUMMARY_URL(branchInQueryString)
      );
      const isSameSchema = currentSchemaHash?.main === newSchemaSummary.main;

      // Updating schema only if it's different from the current one
      if (isSameSchema) return;

      setCurrentSchemaHash(newSchemaSummary);
      await fetchAndSetSchema();
    } catch (error) {
      console.error("Error while updating the schema state:", error);
    }
  };

  useEffect(() => {
    updateSchemaStateIfNeeded();
  }, [branchInQueryString]);

  useEffect(() => {
    const filter = branchInQueryString
      ? (b: Branch) => branchInQueryString === b.name
      : (b: Branch) => b.is_default;
    const selectedBranch = branches.find(filter);
    setCurrentBranch(selectedBranch);
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
