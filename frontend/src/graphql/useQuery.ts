import { useQuery as useApolloQuery } from "@apollo/client";
import { useAtom } from "jotai";
import { branchState } from "../state/atoms/branch.atom";

const useQuery = (QUERY: any, options?: any) => {
  console.log("options: ", options);
  const [branch] = useAtom(branchState);
  console.log("branch: ", branch);

  return useApolloQuery(QUERY, {...options, context: { branch: branch?.name }});
};

export default useQuery;