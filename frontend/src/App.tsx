import { useAtom } from "jotai";
import * as R from "ramda";
import { useCallback, useEffect } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { toast } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import { StringParam, useQueryParam } from "use-query-params";
import { ALERT_TYPES, Alert } from "./components/alert";
import { CONFIG } from "./config/config";
import { MAIN_ROUTES } from "./config/constants";
import { QSP } from "./config/qsp";
import { withAuth } from "./decorators/withAuth";
import { branchVar } from "./graphql/variables/branchVar";
import Layout from "./screens/layout/layout";
import { branchesState } from "./state/atoms/branches.atom";
import {
  genericSchemaState,
  genericsState,
  iGenericSchema,
  iGenericSchemaMapping,
  iNodeSchema,
  schemaState,
} from "./state/atoms/schema.atom";
import { schemaKindNameState } from "./state/atoms/schemaKindName.atom";
import "./styles/index.css";
import { sortByOrderWeight } from "./utils/common";
import { fetchUrl } from "./utils/fetch";

function App() {
  const [branches] = useAtom(branchesState);
  const [, setSchema] = useAtom(schemaState);
  const [, setGenerics] = useAtom(genericsState);
  const [, setGenericSchema] = useAtom(genericSchemaState);
  const [, setSchemaKindNameState] = useAtom(schemaKindNameState);
  const [branchInQueryString] = useQueryParam(QSP.BRANCH, StringParam);

  /**
   * Fetch schema from the backend, sort, and return them
   */
  const fetchSchema = useCallback(async () => {
    const sortByName = R.sortBy(R.compose(R.toLower, R.prop("name")));
    try {
      const data = await fetchUrl(CONFIG.SCHEMA_URL(branchInQueryString));

      return {
        schema: sortByName(data.nodes || []),
        generics: sortByName(data.generics || []),
      };
    } catch (err) {
      toast(
        <Alert
          type={ALERT_TYPES.ERROR}
          message={"Something went wrong when fetching the schema details"}
        />
      );
      console.error("Error while fetching the schema: ", err);
      return {
        schema: [],
        generics: [],
      };
    }
  }, [branchInQueryString]);

  /**
   * Set schema in state atom
   */
  const setSchemaInState = useCallback(async () => {
    try {
      const { schema, generics }: { schema: iNodeSchema[]; generics: iGenericSchema[] } =
        await fetchSchema();

      schema.forEach((s) => {
        s.attributes = sortByOrderWeight(s.attributes || []);
        s.relationships = sortByOrderWeight(s.relationships || []);
      });

      setSchema(schema);
      setGenerics(generics);

      const schemaNames = R.map(R.prop("name"), schema);
      const schemaKinds = R.map(R.prop("kind"), schema);
      const schemaKindNameTuples = R.zip(schemaKinds, schemaNames);
      const schemaKindNameMap = R.fromPairs(schemaKindNameTuples);

      setSchemaKindNameState(schemaKindNameMap);

      const genericSchemaMapping: iGenericSchemaMapping = {};

      schema.forEach((schemaNode: any) => {
        if (schemaNode.used_by?.length) {
          genericSchemaMapping[schemaNode.name] = schemaNode.used_by;
        }
      });

      setGenericSchema(genericSchemaMapping);
    } catch (error) {
      toast(
        <Alert type={ALERT_TYPES.ERROR} message={"Something went wrong when fetching the schema"} />
      );

      console.error("Error while fetching the schema: ", error);
    }
  }, []);

  useEffect(() => {
    setSchemaInState();
  }, [branches?.length, branchInQueryString]);

  // useEffect(() => {
  if (branches?.length) {
    // For first load or navigation with branch change:
    // We need to store the current branch in the state, from the QSP or the default branch
    const selectedBranch = branches.find((b) =>
      branchInQueryString ? b.name === branchInQueryString : b.is_default
    );

    if (selectedBranch?.name) {
      // TODO: Fix the bad set state,
      // TODO: mandatory for now to correctly define the apollo context
      branchVar(selectedBranch);
    }
  }
  // }, [branches?.length, branchInQueryString]);

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
