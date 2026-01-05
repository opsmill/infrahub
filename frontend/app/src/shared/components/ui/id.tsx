import { gql } from "@apollo/client";

import useQuery from "@/shared/api/graphql/useQuery";
import { Clipboard } from "@/shared/components/buttons/clipboard";
import { BadgeCircle, CIRCLE_BADGE_TYPES } from "@/shared/components/display/badge-circle";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { NODE_OBJECT } from "@/shared/config/constants";

import { getObjectDisplayLabel } from "@/entities/nodes/api/getObjectDisplayLabel";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";

type tId = {
  id: string;
  kind?: string;
  preventCopy?: boolean;
};

export const Id = (props: tId) => {
  const { id, kind = NODE_OBJECT, preventCopy } = props;

  const queryString = getObjectDisplayLabel({ kind });

  const query = gql`
    ${queryString}
  `;

  const { loading, error, data } = useQuery(query, { variables: { ids: [id] } });

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
