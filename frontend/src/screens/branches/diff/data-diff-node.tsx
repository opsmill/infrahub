import { useNavigate, useParams } from "react-router-dom";
import Accordion from "../../../components/accordion";
import { BADGE_TYPES, Badge } from "../../../components/badge";
import { DateDisplay } from "../../../components/date-display";
import { DataDiffAttribute } from "./data-diff-attribute";
import { getObjectUrl } from "../../../utils/objects";
import { Link } from "../../../components/link";

export type tDataDiffNodeAttributePropertyValue = {
  new: string;
  previous: string;
}

export type tDataDiffNodeAttributeProperty = {
  type: string;
  changed_at: number;
  action: string;
  value: tDataDiffNodeAttributePropertyValue;
}

export type tDataDiffNodeAttribute = {
  name?: string;
  changed_at?: number;
  action?: string;
  properties?: tDataDiffNodeAttributeProperty[];
}

export type tDataDiffNode = {
  display_label: string;
  id: string;
  action: string;
  kind: string;
  changed_at?: number;
  attributes: tDataDiffNodeAttribute[];
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

  const { branchname } = useParams();
  const navigate = useNavigate();

  const {
    id,
    display_label,
    action,
    kind,
    changed_at,
    attributes = [],
  } = node;

  const title = (
    <div className="flex">
      <Badge className="mr-2" type={getBadgeType(node?.action)}>
        {action?.toUpperCase()}
      </Badge>

      <Badge className="mr-2">
        {kind}
      </Badge>

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
        <div className="m-4 flex">
          <Link onClick={() => navigate(getObjectUrl({ kind, id, branch: branchname }))}>
          ID: {id}
          </Link>
        </div>

        <div>
          {
            attributes
            ?.map(
              (attribute: tDataDiffNodeAttribute, index: number) => (
                <DataDiffAttribute key={index} attribute={attribute} />
              )
            )
          }
        </div>
      </Accordion>
    </div>
  );
};