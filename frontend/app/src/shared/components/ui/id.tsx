import { gql } from "@apollo/client";

import useQuery from "@/shared/api/graphql/useQuery";
import { Clipboard } from "@/shared/components/buttons/clipboard";
import { BadgeCircle, CIRCLE_BADGE_TYPES } from "@/shared/components/display/badge-circle";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { CONFIG } from "@/shared/config/config";
import { NODE_OBJECT } from "@/shared/config/constants";

import { getObjectDisplayLabel } from "@/entities/nodes/api/getObjectDisplayLabel";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";

type tId = {
  id: string;
  kind?: string;
  branch?: string | null;
  date?: Date | null;
  preventCopy?: boolean;
  // Pre-resolved display label. When provided, the component renders it and
  // skips its own GraphQL query — required when rendering many ids at once
  // to avoid the per-item fan-out described in #9067.
  label?: string;
  // When true, renders a loading indicator without firing an internal query.
  // Used by callers that resolve labels in a parent batch.
  loading?: boolean;
};

export const Id = ({
  id,
  kind = NODE_OBJECT,
  preventCopy,
  branch,
  date,
  label,
  loading: externalLoading,
}: tId) => {
  const skipFetch = label !== undefined || !!externalLoading;

  const { loading, error, data } = useQuery(gql(getObjectDisplayLabel({ kind })), {
    variables: { ids: [id] },
    context: { uri: CONFIG.GRAPHQL_URL(branch, date) },
    skip: skipFetch,
  });

  const renderBadge = (content: React.ReactNode) => (
    <BadgeCircle type={CIRCLE_BADGE_TYPES.LIGHT}>
      {content}

      {!preventCopy && (
        <Clipboard
          value={id}
          alert="ID copied!"
          tooltip="Copy ID"
          className="ml-2 rounded-full p-1"
        />
      )}
    </BadgeCircle>
  );

  if (externalLoading) {
    return <LoadingIndicator />;
  }

  if (label !== undefined) {
    return renderBadge(label);
  }

  const object = data?.[kind]?.edges?.[0]?.node ?? {};

  if (loading) {
    return <LoadingIndicator />;
  }

  if (error || !getNodeLabel(object)) {
    return <BadgeCircle type={CIRCLE_BADGE_TYPES.LIGHT}>Name not found</BadgeCircle>;
  }

  return renderBadge(getNodeLabel(object));
};
