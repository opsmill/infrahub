export interface iSchemaAttributeData {
  value: string;
  source: {
    id: string;
    display_label: string;
    __typename: string;
  };
  owner: {
    id: string;
    display_label: string;
    __typename: string;
  };
  is_visible: boolean;
  is_protected: boolean;
}

export interface iSchemaRelationshipData {
  id: string;
  _relation__source: {
    id: string;
    display_label: string;
    __typename: string;
  };
  _relation__owner: {
    id: string;
    display_label: string;
    __typename: string;
  };
  _relation__is_visible: boolean;
  _relation__is_protected: boolean;
}
