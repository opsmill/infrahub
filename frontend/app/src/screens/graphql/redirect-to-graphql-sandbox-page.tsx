import { constructPath } from "@/utils/fetch";
import { Navigate, useLocation, useParams } from "react-router-dom";

const RedirectToGraphqlSandboxPage = () => {
  const { branch } = useParams();
  const location = useLocation();

  return (
    <Navigate
      to={constructPath("/graphql", [{ name: "branch", value: branch }])}
      state={{ from: location }}
      replace
    />
  );
};

export function Component() {
  return <RedirectToGraphqlSandboxPage />;
}
