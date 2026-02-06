import { graphql } from "gql.tada";

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
};

export const Id = ({ id, kind = NODE_OBJECT, preventCopy, branch, date }: tId) => {
  const { loading, error, data } = useQuery(graphql(getObjectDisplayLabel({ kind })), {
    variables: { ids: [id] },
    context: { uri: CONFIG.GRAPHQL_URL(branch, date) },
  });

  const object = data?.[kind]?.edges?.[0]?.node ?? {};

  if (loading) {
    return <LoadingIndicator />;
  }

  if (error || !getNodeLabel(object)) {
    return <BadgeCircle type={CIRCLE_BADGE_TYPES.LIGHT}>Name not found</BadgeCircle>;
  }

  return (
    <BadgeCircle type={CIRCLE_BADGE_TYPES.LIGHT}>
      {getNodeLabel(object)}

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
};
