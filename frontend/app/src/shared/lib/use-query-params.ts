import { use } from "react";
import {
  UNSAFE_DataRouterContext,
  UNSAFE_NavigationContext,
  useLocation,
  useNavigate,
} from "react-router";
import { QueryParamAdapter } from "use-query-params";

// https://github.com/pbeshai/use-query-params/issues/295#issuecomment-2506132034
export const ReactRouter7Adapter = ({
  children,
}: {
  children: (adapter: QueryParamAdapter) => React.ReactElement | null;
}) => {
  // we need the navigator directly so we can access the current version
  // of location in case of multiple updates within a render (e.g. #233)
  // but we will limit our usage of it and have a backup to just use
  // useLocation() output in case of some kind of breaking change we miss.
  // see: https://github.com/remix-run/react-router/blob/f3d87dcc91fbd6fd646064b88b4be52c15114603/packages/react-router-dom/index.tsx#L113-L131
  const { navigator } = use(UNSAFE_NavigationContext);
  const navigate = useNavigate();
  const router = use(UNSAFE_DataRouterContext)?.router;
  const location = useLocation();

  const adapter: QueryParamAdapter = {
    replace(location) {
      navigate(location.search || "?", {
        replace: true,
        state: location.state,
      });
    },
    push(location) {
      navigate(location.search || "?", {
        replace: false,
        state: location.state,
      });
    },
    get location() {
      // be a bit defensive here in case of an unexpected breaking change in React Router
      return router?.state?.location ?? navigator?.location ?? location;
    },
  };

  return children(adapter);
};
