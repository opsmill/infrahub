import Handlebars from "handlebars";

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
export const getDropdownOptionsForRelatedPeers = Handlebars.compile(`query DropdownFormOptions {
    {{#each peers}}
    {{this}} {
        id
        display_label
    }
    {{/each}}
}`);
