import { useLocation, useNavigate } from "react-router";
import type { PartialLocation, QueryParamAdapterComponent } from "use-query-params";

// https://github.com/pbeshai/use-query-params/issues/295#issuecomment-2788874576
export const ReactRouter7Adapter: QueryParamAdapterComponent = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();

  return children({
    location,
    push: ({ search, state }: PartialLocation) => navigate({ search }, { state }),
    replace: ({ search, state }: PartialLocation) => navigate({ search }, { replace: true, state }),
  });
};
