import { addCollection } from "@iconify-icon/react";
import mdiIcons from "@iconify-json/mdi/icons.json";
import { useAtomValue } from "jotai";
import { useContext, useEffect } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import "react-toastify/dist/ReactToastify.css";
import { StringParam, useQueryParam } from "use-query-params";
import { QSP } from "./config/qsp";
import { MAIN_ROUTES } from "./config/routes";
import { withAuth } from "./decorators/withAuth";
import Layout from "./screens/layout/layout";
import { branchesState } from "./state/atoms/branches.atom";

import { SchemaContext, withSchemaContext } from "./decorators/withSchemaContext";
import "./styles/index.css";
addCollection(mdiIcons);

const App = () => {
  const branches = useAtomValue(branchesState);
  const [branchInQueryString] = useQueryParam(QSP.BRANCH, StringParam);
  const { checkSchemaUpdate } = useContext(SchemaContext);

  useEffect(() => {
    checkSchemaUpdate();
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
};

export default withSchemaContext(withAuth(App));
