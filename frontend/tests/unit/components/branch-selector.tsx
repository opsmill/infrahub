import { StringParam, useQueryParam } from "use-query-params";
import { Button } from "../../../src/components/button";
import { QSP } from "../../../src/config/qsp";

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
