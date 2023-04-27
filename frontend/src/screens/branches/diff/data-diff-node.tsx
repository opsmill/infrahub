import { useNavigate, useParams } from "react-router-dom";
import Accordion from "../../../components/accordion";
import { BADGE_TYPES, Badge } from "../../../components/badge";
import { DateDisplay } from "../../../components/date-display";
import { DataDiffAttribute } from "./data-diff-attribute";
import { getObjectUrl } from "../../../utils/objects";
import { constructPath } from "../../../utils/fetch";
import { Tooltip } from "../../../components/tooltip";
import { useAtom } from "jotai";
import { schemaState } from "../../../state/atoms/schema.atom";
import { DataDiffRelationship } from "./data-diff-relationship";

export type tDataDiffNodePropertyValue = {
  new: string;
  previous: string;
}

export type tDataDiffNodeProperty = {
  type: string;
  changed_at: number;
  action: string;
  value: tDataDiffNodePropertyValue;
}

export type tDataDiffNodeRelationshipPeer = {
  id: string;
  kind: string;
  display_label?: string;
}

export type tDataDiffNodeAttribute = {
  name?: string;
  changed_at?: number;
  action?: string;
  properties?: tDataDiffNodeProperty[];
}

export type tDataDiffNodeRelationship = {
  branch?: string;
  name?: string;
  changed_at?: number;
  action?: string;
  properties?: tDataDiffNodeProperty[];
  peer?: tDataDiffNodeRelationshipPeer;
}

export type tDataDiffNode = {
  display_label: string;
  id: string;
  action: string;
  kind: string;
  changed_at?: number;
  attributes: tDataDiffNodeAttribute[];
  relationships: tDataDiffNodeAttribute[];
}

export type tDataDiffNodeProps = {
  node: tDataDiffNode,
}

const badgeTypes: { [key: string]: BADGE_TYPES } = {
  added: BADGE_TYPES.VALIDATE,
  updated: BADGE_TYPES.WARNING,
  removed: BADGE_TYPES.CANCEL,
};

export const getBadgeType = (action?: string) => {
  if (!action) return null;

  return badgeTypes[action];
};

export const DataDiffNode = (props: tDataDiffNodeProps) => {
  const { node } = props;

  const {
    id,
    display_label,
    action,
    kind,
    changed_at,
    attributes = [],
    relationships = []
  } = node;

  const { branchname } = useParams();
  const navigate = useNavigate();
  const [schemaList] = useAtom(schemaState);
  const schema = schemaList.filter((s) => s.kind === kind)[0];

  const title = (
    <div className="flex">
      <Badge className="mr-2" type={getBadgeType(node?.action)}>
        {action?.toUpperCase()}
      </Badge>

      <Tooltip message={"Link to the object"}>
        <Badge
          className="mr-2"
          onClick={
            () => {
              console.log("OK");
              navigate(constructPath(getObjectUrl({ kind: schema.name, id, branch: branchname })));
            }
          }
        >
          {kind}
        </Badge>
      </Tooltip>


      <span className="mr-2">
        {display_label}
      </span>

      {
        changed_at
        && (
          <DateDisplay date={changed_at} hideDefault />
        )
      }
    </div>
  );

  return (
    <div className={"rounded-lg shadow p-4 m-4 bg-white"}>
      <Accordion title={title}>
        <div className="">
          {
            attributes?.length
              ? (
                <div className="mb-4">
                  <div>
              Attributes:
                  </div>

                  {
                    attributes
                    ?.map(
                      (attribute: tDataDiffNodeAttribute, index: number) => (
                        <DataDiffAttribute key={index} attribute={attribute} />
                      )
                    )
                  }
                </div>
              )
              : null
          }

          {
            relationships?.length
              ? (
                <div className="">
                  <div>
                      Relationships:
                  </div>

                  {
                    relationships
                    ?.map(
                      (relationship: tDataDiffNodeAttribute, index: number) => (
                        <DataDiffRelationship key={index} relationship={relationship} />
                      )
                    )
                  }
                </div>
              )
              : null
          }
        </div>
      </Accordion>
    </div>
  );
};