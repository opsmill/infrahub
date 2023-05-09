import { gql } from "graphql-request";
import { graphQLClient } from "../graphql/graphqlClient";

declare const Handlebars: any;

export interface iPeerDropdownOption {
  id: string;
  display_label: string;
}

export interface iPeerDropdownOptions {
  [peer: string]: iPeerDropdownOption[];
}

/**
 * Get form options, for each relationshp get all the dropdown options by creating a dynamic query and fetching id and displaylabel
 * Peers -> [status, tag, role, location]
 *
 * Sample output below
 * {
 *    "status": [
 *      { "id": "1", "display_label": "Provisionning" },
 *      { "id": "2", "display_label": "Active" }
 *    ],
 *    "tag": [
 *      { "id": "1", "display_label": "red" },
 *      { "id": "2", "display_label": "green" }
 *    ],
 *    "role": [
 *      { "id": "1", "display_label": "Management" },
 *      { "id": "2", "display_label": "Loopback" }
 *    ],
 *    "location": [
 *      { "id": "1", "display_label": "jfk1" },
 *      { "id": "2", "display_label": "ord1" }
 *    ]
 *  }
 */
const template = Handlebars.compile(`query DropdownFormOptions {
    {{#each peers}}
    {{this}} {
        id
        display_label
    }
    {{/each}}
}`);

const getDropdownOptionsForRelatedPeers = async (
  peers: string[]
): Promise<iPeerDropdownOptions> => {
  if (!peers.length) {
    return {};
  }
  const queryString = template({
    peers: peers.filter((peer) => !!peer),
  });
  const query = gql`
    ${queryString}
  `;
  try {
    return graphQLClient.request(query);
  } catch {
    console.error("Something went wrong while fetching form dropdown option list");
  }
  return {};
};

export default getDropdownOptionsForRelatedPeers;
