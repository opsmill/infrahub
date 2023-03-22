import { useAtom } from "jotai";
import { branchesState } from "../../state/atoms/branches.atom";

export const ListBranches = () => {
  const [branches] = useAtom(branchesState);
  console.log("branches: ", branches);

  return (
    <>
      ok
    </>
  )
}