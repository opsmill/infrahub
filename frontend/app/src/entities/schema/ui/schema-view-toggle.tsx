import { Icon } from "@iconify-icon/react";

import {
  LinkToggleButton,
  LinkToggleButtonGroup,
} from "@/shared/components/buttons/link-toggle-button";

export const SchemaViewToggle = () => (
  <LinkToggleButtonGroup>
    <LinkToggleButton to="/schema">
      <Icon icon="mdi:format-list-bulleted" />
      List
    </LinkToggleButton>
    <LinkToggleButton to="/schema-graph">
      <Icon icon="mdi:graph" />
      Graph
    </LinkToggleButton>
  </LinkToggleButtonGroup>
);
