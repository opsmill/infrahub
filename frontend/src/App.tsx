import { useReactiveVar } from "@apollo/client";
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
  const [, setSchema] = useAtom(schemaState);
  const [, setGenerics] = useAtom(genericsState);
  const [, setGenericSchema] = useAtom(genericSchemaState);
  const [, setSchemaKindNameState] = useAtom(schemaKindNameState);
  const [branchInQueryString] = useQueryParam(QSP.BRANCH, StringParam);
  const branch = useReactiveVar(branchVar);

  /**
   * Fetch schema from the backend, sort, and return them
   */
  const fetchSchema = useCallback(async () => {
    const sortByName = R.sortBy(R.compose(R.toLower, R.prop("name")));
    try {
      const data = await fetchUrl(CONFIG.SCHEMA_URL(branchInQueryString ?? branch?.name));

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
  }, [branch?.name, branchInQueryString]);

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
  }, [fetchSchema, setGenericSchema, setSchema, setSchemaKindNameState, setGenerics]);

  useEffect(() => {
    setSchemaInState();
  }, [setSchemaInState, branch]);

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
