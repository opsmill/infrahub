import type { ReactNode } from "react";

import { ARTIFACT_DEFINITION_OBJECT, ARTIFACT_OBJECT } from "@/config/constants";
import { QSP } from "@/config/qsp";

import type { ArtifactEvent } from "@/shared/api/graphql/generated/graphql";
import { Link } from "@/shared/components/ui/link";

import { NodeLabel } from "@/entities/nodes/object/ui/node-label";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";

const ArtifactTitleContent = (props: ArtifactEvent) => {
  return (
    <>
      <Link
        to={getObjectDetailsUrl(ARTIFACT_OBJECT, props.primary_node?.id, [
          { name: QSP.BRANCH, value: props.branch },
        ])}
        className="text-black"
      >
        <NodeLabel id={props.primary_node?.id} kind={ARTIFACT_OBJECT} />
      </Link>
      from the definition
      <Link
        to={getObjectDetailsUrl(ARTIFACT_DEFINITION_OBJECT, props.artifact_definition_id, [
          { name: QSP.BRANCH, value: props.branch },
        ])}
        className="text-black"
      >
        <NodeLabel id={props.artifact_definition_id} kind={ARTIFACT_DEFINITION_OBJECT} />
      </Link>
    </>
  );
};

export const ARTIFACT_EVENTS_MAPPING: Record<string, (props: ArtifactEvent) => ReactNode> = {
  "infrahub.artifact.created": (props) => {
    return (
      <div className="flex items-center gap-1 text-gray-600">
        created the artifact <ArtifactTitleContent {...props} />
      </div>
    );
  },
  "infrahub.artifact.updated": (props) => {
    return (
      <div className="flex items-center gap-1 text-gray-600">
        updated the artifact
        <ArtifactTitleContent {...props} />
      </div>
    );
  },
};

export const ArtifactEventTitle = (props: ArtifactEvent) => {
  const { event, account_id, branch } = props;

  return (
    <div className="flex flex-wrap items-center gap-1 text-sm">
      <NodeLabel id={account_id} kind="CoreAccount" branch={branch} />

      {ARTIFACT_EVENTS_MAPPING[event] && ARTIFACT_EVENTS_MAPPING[event](props)}
    </div>
  );
};
