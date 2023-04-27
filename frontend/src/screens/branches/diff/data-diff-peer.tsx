import { Badge } from "../../../components/badge";
import { tDataDiffNodeRelationshipPeer } from "./data-diff-node";

export type tDataDiffNodePeerProps = {
  peer: tDataDiffNodeRelationshipPeer,
  branch?: string;
}

export const DataDiffPeer = (props: tDataDiffNodePeerProps) => {
  const { peer } = props;

  const {
    kind,
    display_label,
  } = peer;

  return (
    <div className="flex">
      <div className="flex items-center">
        <Badge className="mr-2">
          {kind}
        </Badge>
      </div>

      <div className="flex items-center">
        <span className="mr-4">
          {display_label}
        </span>
      </div>
    </div>
  );
};