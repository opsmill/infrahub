import { useQuery as useApolloQuery, useReactiveVar } from "@apollo/client";
import { useAtom } from "jotai";
import { branchState } from "../state/atoms/branch.atom";
import { dateVar } from "./variables/dateVar";

const useQuery = (QUERY: any, options?: any) => {
  const [branch] = useAtom(branchState);
  const date = useReactiveVar(dateVar);

  return useApolloQuery(QUERY, { ...options, context: { branch: branch?.name, date } });
};

export default useQuery;
