import { StringParam, useQueryParam } from "use-query-params";
import { QSP } from "../../config/qsp";
import { Button } from "../button";

export default function BranchSelectorTest() {
  const [branchInQueryString, setBranchInQueryString] = useQueryParam(QSP.BRANCH, StringParam);

  return (
    <div>
      <div>
        <Button onClick={() => setBranchInQueryString("test")}>Click me</Button>
      </div>
      <div>{branchInQueryString ?? "main"}</div>
    </div>
  );
}
