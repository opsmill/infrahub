import { constructPath } from "@/utils/fetch";
import { Navigate, useLocation, useParams } from "react-router-dom";

const RedirectToGraphiQLPage = () => {
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

export default RedirectToGraphiQLPage;
