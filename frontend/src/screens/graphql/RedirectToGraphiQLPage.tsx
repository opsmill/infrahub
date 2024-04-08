import { Navigate, useLocation, useParams } from "react-router-dom";
import { constructPath } from "../../utils/fetch";

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
