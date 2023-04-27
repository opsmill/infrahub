import { useNavigate } from "react-router-dom";
import { Badge } from "../../../components/badge";
import { Tooltip } from "../../../components/tooltip";
import { tDataDiffNodeRelationshipPeer } from "./data-diff-node";
import { constructPath } from "../../../utils/fetch";
import { getObjectUrl } from "../../../utils/objects";
import { useAtom } from "jotai";
import { schemaState } from "../../../state/atoms/schema.atom";

export type tDataDiffNodePeerProps = {
  peer: tDataDiffNodeRelationshipPeer,
  branch?: string;
}

export const DataDiffPeer = (props: tDataDiffNodePeerProps) => {
  const { peer, branch } = props;

  const {
    id,
    kind,
    display_label,
  } = peer;

  const [schemaList] = useAtom(schemaState);
  const schema = schemaList.filter((s) => s.kind === kind)[0];

  const navigate = useNavigate();

  return (
    <div className="flex">
      <div className="flex items-center">
        <Tooltip message={"Link to the object"}>
          <Badge
            className="mr-2"
            onClick={
              () => {
                console.log("OK");
                navigate(constructPath(getObjectUrl({ kind: schema.name, id, branch })));
              }
            }
          >
            {kind}
          </Badge>
        </Tooltip>
      </div>

      <div className="flex items-center">
        <span className="mr-4">
          {display_label}
        </span>
      </div>
    </div>
  );
};