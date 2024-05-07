import { gql } from "@apollo/client";
import { NODE_OBJECT } from "../../config/constants";
import { getObjectDisplayLabel } from "../../graphql/queries/objects/getObjectDisplayLabel";
import useQuery from "../../hooks/useQuery";
import LoadingScreen from "../../screens/loading-screen/loading-screen";
import { Clipboard } from "../buttons/clipboard";
import { BadgeCircle, CIRCLE_BADGE_TYPES } from "../display/badge-circle";

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

  const { loading, error, data } = useQuery(query, { variable: { ids: [id] } });

  const object = data?.[kind]?.edges?.[0]?.node ?? {};

  if (loading) {
    return <LoadingScreen hideText size={24} />;
  }

  if (error || !object?.display_label) {
    return <BadgeCircle type={CIRCLE_BADGE_TYPES.LIGHT}>Name not found</BadgeCircle>;
  }

  return (
    <BadgeCircle type={CIRCLE_BADGE_TYPES.LIGHT}>
      {object?.display_label}

      {!preventCopy && (
        <Clipboard
          value={id}
          alert="ID copied!"
          tooltip="Copy ID"
          className="ml-2 p-1 rounded-full"
        />
      )}
    </BadgeCircle>
  );
};
