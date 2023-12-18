import { addCollection } from "@iconify-icon/react";
import mdiIcons from "@iconify-json/mdi/icons.json";
import { useAtom, useAtomValue, useSetAtom } from "jotai";
import { useEffect } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import "react-toastify/dist/ReactToastify.css";
import { StringParam, useQueryParam } from "use-query-params";
import { CONFIG } from "./config/config";
import { QSP } from "./config/qsp";
import { MAIN_ROUTES } from "./config/routes";
import { withAuth } from "./decorators/withAuth";
import { Branch } from "./generated/graphql";
import Layout from "./screens/layout/layout";
import { branchesState, currentBranchAtom } from "./state/atoms/branches.atom";
import {
  schemaSummaryAtom,
  iNodeSchema,
  SchemaSummary,
  schemaFamily,
} from "./state/atoms/schema.atom";
import "./styles/index.css";
import { fetchUrl } from "./utils/fetch";
addCollection(mdiIcons);

function App() {
  const branches = useAtomValue(branchesState);
  const setCurrentBranch = useSetAtom(currentBranchAtom);
  const [currentSchemaHash, setCurrentSchemaHash] = useAtom(schemaSummaryAtom);
  const [branchInQueryString] = useQueryParam(QSP.BRANCH, StringParam);

  const updateSchemaStateIfNeeded = async () => {
    if (!currentSchemaHash) return; // Wait for initial load

    try {
      const newSchemaSummary: SchemaSummary = await fetchUrl(
        CONFIG.SCHEMA_SUMMARY_URL(branchInQueryString)
      );
      const isSameSchema = currentSchemaHash?.main === newSchemaSummary.main;

      // Updating schema only if it's different from the current one
      if (isSameSchema) return;
      const { nodes: currentNodeHashes, generics: currentGenericHashes } = currentSchemaHash;

      const nodesWithDifferentHash = Object.entries(newSchemaSummary.nodes).reduce(
        (result: string[], [key, fetchedValue]) => {
          return currentNodeHashes[key] !== fetchedValue ? [...result, key] : result;
        },
        []
      );

      const genericsWithDifferentHash = Object.entries(newSchemaSummary.generics).reduce(
        (result: string[], [key, fetchedValue]) => {
          return currentGenericHashes[key] !== fetchedValue ? [...result, key] : result;
        },
        []
      );

      console.log([...nodesWithDifferentHash, ...genericsWithDifferentHash]);
      [...nodesWithDifferentHash, ...genericsWithDifferentHash].forEach((kind) => {
        fetchUrl(CONFIG.SCHEMA_KIND_URL(kind, branchInQueryString)).then((node: iNodeSchema) => {
          schemaFamily(node);
        });
      });

      setCurrentSchemaHash(newSchemaSummary);
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
