import type { ReactNode } from "react";

import type { ArtifactEvent } from "@/shared/api/graphql/generated/graphql";
import { Link } from "@/shared/components/ui/link";
import { ARTIFACT_DEFINITION_OBJECT, ARTIFACT_OBJECT } from "@/shared/config/constants";
import { QSP } from "@/shared/config/qsp";

import { NodeLabel } from "@/entities/nodes/object/ui/node-label";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";

const ArtifactTitleContent = (props: ArtifactEvent) => {
  return (
    <>
      <Link
        to={getObjectDetailsUrl(ARTIFACT_OBJECT, props.primary_node?.id, [
          { name: QSP.BRANCH, value: props.branch },
        ])}
        className="min-w-0 truncate text-black"
      >
        <NodeLabel id={props.primary_node?.id} kind={ARTIFACT_OBJECT} />
      </Link>
      <span className="whitespace-nowrap">from the definition</span>
      <Link
        to={getObjectDetailsUrl(ARTIFACT_DEFINITION_OBJECT, props.artifact_definition_id, [
          { name: QSP.BRANCH, value: props.branch },
        ])}
        className="min-w-0 truncate text-black"
      >
        <NodeLabel id={props.artifact_definition_id} kind={ARTIFACT_DEFINITION_OBJECT} />
      </Link>
    </>
  );
};

export const ARTIFACT_EVENTS_MAPPING: Record<string, (props: ArtifactEvent) => ReactNode> = {
  "infrahub.artifact.created": (props) => {
    return (
      <div className="flex min-w-0 items-center gap-1 overflow-hidden text-gray-600">
        <span className="whitespace-nowrap">created the artifact</span>
        <ArtifactTitleContent {...props} />
      </div>
    );
  },
  "infrahub.artifact.updated": (props) => {
    return (
      <div className="flex min-w-0 items-center gap-1 overflow-hidden text-gray-600">
        <span className="whitespace-nowrap">updated the artifact</span>
        <ArtifactTitleContent {...props} />
      </div>
    );
  },
};

export const ArtifactEventTitle = (props: ArtifactEvent) => {
  const { event, account_id, branch } = props;

  return (
    <div className="flex w-full min-w-0 items-center gap-1 overflow-hidden text-sm">
      {account_id ? (
        <span className="max-w-[200px] shrink-0 truncate">
          <NodeLabel id={account_id} kind="CoreAccount" branch={branch} />
        </span>
      ) : (
        "-"
      )}

      {ARTIFACT_EVENTS_MAPPING[event] && ARTIFACT_EVENTS_MAPPING[event](props)}
    </div>
  );
};
