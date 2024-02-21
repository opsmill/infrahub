import { addCollection } from "@iconify-icon/react";
import mdiIcons from "@iconify-json/mdi/icons.json";
import { Navigate, Route, Routes } from "react-router-dom";
import "react-toastify/dist/ReactToastify.css";
import { AuthProvider, RequireAuth } from "./decorators/auth";
import { MAIN_ROUTES } from "./config/routes";
import Layout from "./screens/layout/layout";
import SignIn from "./screens/sign-in/sign-in";

addCollection(mdiIcons);

const App = () => {
  return (
    <AuthProvider>
      <Routes>
        <Route
          path="/"
          element={
            <RequireAuth>
              <Layout />
            </RequireAuth>
          }>
          {MAIN_ROUTES.map((route) => (
            <Route index key={route.path} path={route.path} element={route.element} />
          ))}
          <Route path="*" element={<Navigate to="/" />} />
        </Route>
        <Route path="/signin" element={<SignIn />} />
      </Routes>
    </AuthProvider>
  );
};

export default App;
