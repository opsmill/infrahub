export type Maybe<T> = T | null;
export type InputMaybe<T> = Maybe<T>;
export type Exact<T extends { [key: string]: unknown }> = {
  [K in keyof T]: T[K];
};
export type MakeOptional<T, K extends keyof T> = Omit<T, K> & {
  [SubKey in K]?: Maybe<T[SubKey]>;
};
export type MakeMaybe<T, K extends keyof T> = Omit<T, K> & {
  [SubKey in K]: Maybe<T[SubKey]>;
};
/** All built-in and custom scalars, mapped to their actual values */
export type Scalars = {
  ID: string;
  String: string;
  Boolean: boolean;
  Int: number;
  Float: number;
  DateTime: any;
  GenericScalar: any;
};

export type Account = DataOwner &
  DataSource & {
    __typename?: "Account";
    _updated_at?: Maybe<Scalars["DateTime"]>;
    description?: Maybe<StrAttribute>;
    groups: Array<Maybe<RelatedGroup>>;
    id: Scalars["String"];
    name: StrAttribute;
    tokens: Array<Maybe<RelatedAccountToken>>;
    type: StrAttribute;
  };

export type AccountGroupsArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
};

export type AccountTokensArgs = {
  expiration_date__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
  token__value?: InputMaybe<Scalars["String"]>;
};

export type AccountCreate = {
  __typename?: "AccountCreate";
  object?: Maybe<Account>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type AccountCreateInput = {
  description?: InputMaybe<StringAttributeInput>;
  groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  id?: InputMaybe<Scalars["String"]>;
  name: StringAttributeInput;
  tokens?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  type?: InputMaybe<StringAttributeInput>;
};

export type AccountDelete = {
  __typename?: "AccountDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

export type AccountToken = {
  __typename?: "AccountToken";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  account?: Maybe<RelatedAccount>;
  expiration_date?: Maybe<StrAttribute>;
  id: Scalars["String"];
  token: StrAttribute;
};

export type AccountTokenCreate = {
  __typename?: "AccountTokenCreate";
  object?: Maybe<AccountToken>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type AccountTokenCreateInput = {
  account: RelatedNodeInput;
  expiration_date?: InputMaybe<StringAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  token: StringAttributeInput;
};

export type AccountTokenDelete = {
  __typename?: "AccountTokenDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

export type AccountTokenUpdate = {
  __typename?: "AccountTokenUpdate";
  object?: Maybe<AccountToken>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type AccountTokenUpdateInput = {
  account?: InputMaybe<RelatedNodeInput>;
  expiration_date?: InputMaybe<StringAttributeInput>;
  id: Scalars["String"];
  token?: InputMaybe<StringAttributeInput>;
};

export type AccountUpdate = {
  __typename?: "AccountUpdate";
  object?: Maybe<Account>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type AccountUpdateInput = {
  description?: InputMaybe<StringAttributeInput>;
  groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  id: Scalars["String"];
  name?: InputMaybe<StringAttributeInput>;
  tokens?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  type?: InputMaybe<StringAttributeInput>;
};

/** Attribute of type GenericScalar */
export type AnyAttribute = AttributeInterface & {
  __typename?: "AnyAttribute";
  id?: Maybe<Scalars["String"]>;
  is_inherited?: Maybe<Scalars["Boolean"]>;
  is_protected?: Maybe<Scalars["Boolean"]>;
  is_visible?: Maybe<Scalars["Boolean"]>;
  owner?: Maybe<DataOwner>;
  source?: Maybe<DataSource>;
  updated_at?: Maybe<Scalars["DateTime"]>;
  value?: Maybe<Scalars["GenericScalar"]>;
};

export type AnyAttributeInput = {
  is_protected?: InputMaybe<Scalars["Boolean"]>;
  is_visible?: InputMaybe<Scalars["Boolean"]>;
  owner?: InputMaybe<Scalars["String"]>;
  source?: InputMaybe<Scalars["String"]>;
  value?: InputMaybe<Scalars["GenericScalar"]>;
};

export type AttributeInterface = {
  is_inherited?: Maybe<Scalars["Boolean"]>;
  is_protected?: Maybe<Scalars["Boolean"]>;
  is_visible?: Maybe<Scalars["Boolean"]>;
  updated_at?: Maybe<Scalars["DateTime"]>;
};

export type AttributeSchema = {
  __typename?: "AttributeSchema";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  branch: BoolAttribute;
  default_value?: Maybe<AnyAttribute>;
  description?: Maybe<StrAttribute>;
  id: Scalars["String"];
  inherited: BoolAttribute;
  kind: StrAttribute;
  label?: Maybe<StrAttribute>;
  name: StrAttribute;
  optional: BoolAttribute;
  unique: BoolAttribute;
};

export type AttributeSchemaCreate = {
  __typename?: "AttributeSchemaCreate";
  object?: Maybe<AttributeSchema>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type AttributeSchemaCreateInput = {
  branch: BoolAttributeInput;
  default_value?: InputMaybe<AnyAttributeInput>;
  description?: InputMaybe<StringAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  inherited: BoolAttributeInput;
  kind: StringAttributeInput;
  label?: InputMaybe<StringAttributeInput>;
  name: StringAttributeInput;
  optional: BoolAttributeInput;
  unique: BoolAttributeInput;
};

export type AttributeSchemaDelete = {
  __typename?: "AttributeSchemaDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

export type AttributeSchemaUpdate = {
  __typename?: "AttributeSchemaUpdate";
  object?: Maybe<AttributeSchema>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type AttributeSchemaUpdateInput = {
  branch?: InputMaybe<BoolAttributeInput>;
  default_value?: InputMaybe<AnyAttributeInput>;
  description?: InputMaybe<StringAttributeInput>;
  id: Scalars["String"];
  inherited?: InputMaybe<BoolAttributeInput>;
  kind?: InputMaybe<StringAttributeInput>;
  label?: InputMaybe<StringAttributeInput>;
  name?: InputMaybe<StringAttributeInput>;
  optional?: InputMaybe<BoolAttributeInput>;
  unique?: InputMaybe<BoolAttributeInput>;
};

export type AutonomousSystem = {
  __typename?: "AutonomousSystem";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  asn: IntAttribute;
  description?: Maybe<StrAttribute>;
  id: Scalars["String"];
  name: StrAttribute;
  organization?: Maybe<RelatedOrganization>;
};

export type AutonomousSystemCreate = {
  __typename?: "AutonomousSystemCreate";
  object?: Maybe<AutonomousSystem>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type AutonomousSystemCreateInput = {
  asn: IntAttributeInput;
  description?: InputMaybe<StringAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  name: StringAttributeInput;
  organization: RelatedNodeInput;
};

export type AutonomousSystemDelete = {
  __typename?: "AutonomousSystemDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

export type AutonomousSystemUpdate = {
  __typename?: "AutonomousSystemUpdate";
  object?: Maybe<AutonomousSystem>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type AutonomousSystemUpdateInput = {
  asn?: InputMaybe<IntAttributeInput>;
  description?: InputMaybe<StringAttributeInput>;
  id: Scalars["String"];
  name?: InputMaybe<StringAttributeInput>;
  organization?: InputMaybe<RelatedNodeInput>;
};

export type BgpPeerGroup = {
  __typename?: "BGPPeerGroup";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  description?: Maybe<StrAttribute>;
  export_policies?: Maybe<StrAttribute>;
  id: Scalars["String"];
  import_policies?: Maybe<StrAttribute>;
  local_as?: Maybe<RelatedAutonomousSystem>;
  name: StrAttribute;
  remote_as?: Maybe<RelatedAutonomousSystem>;
};

export type BgpPeerGroupCreate = {
  __typename?: "BGPPeerGroupCreate";
  object?: Maybe<BgpPeerGroup>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type BgpPeerGroupCreateInput = {
  description?: InputMaybe<StringAttributeInput>;
  export_policies?: InputMaybe<StringAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  import_policies?: InputMaybe<StringAttributeInput>;
  local_as?: InputMaybe<RelatedNodeInput>;
  name: StringAttributeInput;
  remote_as?: InputMaybe<RelatedNodeInput>;
};

export type BgpPeerGroupDelete = {
  __typename?: "BGPPeerGroupDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

export type BgpPeerGroupUpdate = {
  __typename?: "BGPPeerGroupUpdate";
  object?: Maybe<BgpPeerGroup>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type BgpPeerGroupUpdateInput = {
  description?: InputMaybe<StringAttributeInput>;
  export_policies?: InputMaybe<StringAttributeInput>;
  id: Scalars["String"];
  import_policies?: InputMaybe<StringAttributeInput>;
  local_as?: InputMaybe<RelatedNodeInput>;
  name?: InputMaybe<StringAttributeInput>;
  remote_as?: InputMaybe<RelatedNodeInput>;
};

export type BgpSession = {
  __typename?: "BGPSession";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  description?: Maybe<StrAttribute>;
  device?: Maybe<RelatedDevice>;
  export_policies?: Maybe<StrAttribute>;
  id: Scalars["String"];
  import_policies?: Maybe<StrAttribute>;
  local_as?: Maybe<RelatedAutonomousSystem>;
  local_ip?: Maybe<RelatedIpAddress>;
  peer_group?: Maybe<RelatedBgpPeerGroup>;
  peer_session?: Maybe<RelatedBgpSession>;
  remote_as?: Maybe<RelatedAutonomousSystem>;
  remote_ip?: Maybe<RelatedIpAddress>;
  role?: Maybe<RelatedRole>;
  status?: Maybe<RelatedStatus>;
  type: StrAttribute;
};

export type BgpSessionCreate = {
  __typename?: "BGPSessionCreate";
  object?: Maybe<BgpSession>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type BgpSessionCreateInput = {
  description?: InputMaybe<StringAttributeInput>;
  device?: InputMaybe<RelatedNodeInput>;
  export_policies?: InputMaybe<StringAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  import_policies?: InputMaybe<StringAttributeInput>;
  local_as?: InputMaybe<RelatedNodeInput>;
  local_ip?: InputMaybe<RelatedNodeInput>;
  peer_group?: InputMaybe<RelatedNodeInput>;
  peer_session?: InputMaybe<RelatedNodeInput>;
  remote_as?: InputMaybe<RelatedNodeInput>;
  remote_ip?: InputMaybe<RelatedNodeInput>;
  role: RelatedNodeInput;
  status: RelatedNodeInput;
  type: StringAttributeInput;
};

export type BgpSessionDelete = {
  __typename?: "BGPSessionDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

export type BgpSessionUpdate = {
  __typename?: "BGPSessionUpdate";
  object?: Maybe<BgpSession>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type BgpSessionUpdateInput = {
  description?: InputMaybe<StringAttributeInput>;
  device?: InputMaybe<RelatedNodeInput>;
  export_policies?: InputMaybe<StringAttributeInput>;
  id: Scalars["String"];
  import_policies?: InputMaybe<StringAttributeInput>;
  local_as?: InputMaybe<RelatedNodeInput>;
  local_ip?: InputMaybe<RelatedNodeInput>;
  peer_group?: InputMaybe<RelatedNodeInput>;
  peer_session?: InputMaybe<RelatedNodeInput>;
  remote_as?: InputMaybe<RelatedNodeInput>;
  remote_ip?: InputMaybe<RelatedNodeInput>;
  role?: InputMaybe<RelatedNodeInput>;
  status?: InputMaybe<RelatedNodeInput>;
  type?: InputMaybe<StringAttributeInput>;
};

/** Attribute of type Boolean */
export type BoolAttribute = AttributeInterface & {
  __typename?: "BoolAttribute";
  id?: Maybe<Scalars["String"]>;
  is_inherited?: Maybe<Scalars["Boolean"]>;
  is_protected?: Maybe<Scalars["Boolean"]>;
  is_visible?: Maybe<Scalars["Boolean"]>;
  owner?: Maybe<DataOwner>;
  source?: Maybe<DataSource>;
  updated_at?: Maybe<Scalars["DateTime"]>;
  value?: Maybe<Scalars["Boolean"]>;
};

export type BoolAttributeInput = {
  is_protected?: InputMaybe<Scalars["Boolean"]>;
  is_visible?: InputMaybe<Scalars["Boolean"]>;
  owner?: InputMaybe<Scalars["String"]>;
  source?: InputMaybe<Scalars["String"]>;
  value?: InputMaybe<Scalars["Boolean"]>;
};

/** Branch */
export type Branch = {
  __typename?: "Branch";
  branched_from?: Maybe<Scalars["String"]>;
  created_at?: Maybe<Scalars["String"]>;
  description?: Maybe<Scalars["String"]>;
  id: Scalars["String"];
  is_data_only?: Maybe<Scalars["Boolean"]>;
  is_default?: Maybe<Scalars["Boolean"]>;
  is_isolated?: Maybe<Scalars["Boolean"]>;
  name: Scalars["String"];
  origin_branch?: Maybe<Scalars["String"]>;
};

export type BranchCreate = {
  __typename?: "BranchCreate";
  object?: Maybe<Branch>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type BranchCreateInput = {
  branched_from?: InputMaybe<Scalars["String"]>;
  description?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["String"]>;
  is_data_only?: InputMaybe<Scalars["Boolean"]>;
  name: Scalars["String"];
  origin_branch?: InputMaybe<Scalars["String"]>;
};

export type BranchDiffAttributeType = {
  __typename?: "BranchDiffAttributeType";
  action?: Maybe<Scalars["String"]>;
  changed_at?: Maybe<Scalars["String"]>;
  id?: Maybe<Scalars["String"]>;
  name?: Maybe<Scalars["String"]>;
  properties?: Maybe<Array<Maybe<BranchDiffPropertyType>>>;
};

export type BranchDiffFileType = {
  __typename?: "BranchDiffFileType";
  action?: Maybe<Scalars["String"]>;
  branch?: Maybe<Scalars["String"]>;
  location?: Maybe<Scalars["String"]>;
  repository?: Maybe<Scalars["String"]>;
};

export type BranchDiffNodeType = {
  __typename?: "BranchDiffNodeType";
  action?: Maybe<Scalars["String"]>;
  attributes?: Maybe<Array<Maybe<BranchDiffAttributeType>>>;
  branch?: Maybe<Scalars["String"]>;
  changed_at?: Maybe<Scalars["String"]>;
  id?: Maybe<Scalars["String"]>;
  kind?: Maybe<Scalars["String"]>;
};

export type BranchDiffPropertyType = {
  __typename?: "BranchDiffPropertyType";
  action?: Maybe<Scalars["String"]>;
  branch?: Maybe<Scalars["String"]>;
  changed_at?: Maybe<Scalars["String"]>;
  type?: Maybe<Scalars["String"]>;
  value?: Maybe<BranchDiffPropertyValueType>;
};

export type BranchDiffPropertyValueType = {
  __typename?: "BranchDiffPropertyValueType";
  new?: Maybe<Scalars["GenericScalar"]>;
  previous?: Maybe<Scalars["GenericScalar"]>;
};

export type BranchDiffRelationshipEdgeNodeType = {
  __typename?: "BranchDiffRelationshipEdgeNodeType";
  id?: Maybe<Scalars["String"]>;
  kind?: Maybe<Scalars["String"]>;
};

export type BranchDiffRelationshipType = {
  __typename?: "BranchDiffRelationshipType";
  action?: Maybe<Scalars["String"]>;
  branch?: Maybe<Scalars["String"]>;
  changed_at?: Maybe<Scalars["String"]>;
  id?: Maybe<Scalars["String"]>;
  name?: Maybe<Scalars["String"]>;
  nodes?: Maybe<Array<Maybe<BranchDiffRelationshipEdgeNodeType>>>;
  properties?: Maybe<Array<Maybe<BranchDiffPropertyType>>>;
};

export type BranchDiffType = {
  __typename?: "BranchDiffType";
  files?: Maybe<Array<Maybe<BranchDiffFileType>>>;
  nodes?: Maybe<Array<Maybe<BranchDiffNodeType>>>;
  relationships?: Maybe<Array<Maybe<BranchDiffRelationshipType>>>;
};

export type BranchMerge = {
  __typename?: "BranchMerge";
  object?: Maybe<Branch>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type BranchNameInput = {
  name?: InputMaybe<Scalars["String"]>;
};

export type BranchRebase = {
  __typename?: "BranchRebase";
  object?: Maybe<Branch>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type BranchValidate = {
  __typename?: "BranchValidate";
  messages?: Maybe<Array<Maybe<Scalars["String"]>>>;
  object?: Maybe<Branch>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type Check = {
  __typename?: "Check";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  class_name: StrAttribute;
  description?: Maybe<StrAttribute>;
  file_path: StrAttribute;
  id: Scalars["String"];
  name: StrAttribute;
  query?: Maybe<RelatedGraphQlQuery>;
  rebase: BoolAttribute;
  repository?: Maybe<RelatedRepository>;
  tags: Array<Maybe<RelatedTag>>;
  timeout: IntAttribute;
};

export type CheckTagsArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
};

export type CheckCreate = {
  __typename?: "CheckCreate";
  object?: Maybe<Check>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CheckCreateInput = {
  class_name: StringAttributeInput;
  description?: InputMaybe<StringAttributeInput>;
  file_path: StringAttributeInput;
  id?: InputMaybe<Scalars["String"]>;
  name: StringAttributeInput;
  query?: InputMaybe<RelatedNodeInput>;
  rebase: BoolAttributeInput;
  repository: RelatedNodeInput;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  timeout?: InputMaybe<IntAttributeInput>;
};

export type CheckDelete = {
  __typename?: "CheckDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CheckUpdate = {
  __typename?: "CheckUpdate";
  object?: Maybe<Check>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CheckUpdateInput = {
  class_name?: InputMaybe<StringAttributeInput>;
  description?: InputMaybe<StringAttributeInput>;
  file_path?: InputMaybe<StringAttributeInput>;
  id: Scalars["String"];
  name?: InputMaybe<StringAttributeInput>;
  query?: InputMaybe<RelatedNodeInput>;
  rebase?: InputMaybe<BoolAttributeInput>;
  repository?: InputMaybe<RelatedNodeInput>;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  timeout?: InputMaybe<IntAttributeInput>;
};

export type Circuit = {
  __typename?: "Circuit";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  circuit_id: StrAttribute;
  description?: Maybe<StrAttribute>;
  endpoints: Array<Maybe<RelatedCircuitEndpoint>>;
  id: Scalars["String"];
  provider?: Maybe<RelatedOrganization>;
  role?: Maybe<RelatedRole>;
  status?: Maybe<RelatedStatus>;
  vendor_id?: Maybe<StrAttribute>;
};

export type CircuitEndpointsArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
};

export type CircuitCreate = {
  __typename?: "CircuitCreate";
  object?: Maybe<Circuit>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CircuitCreateInput = {
  circuit_id: StringAttributeInput;
  description?: InputMaybe<StringAttributeInput>;
  endpoints?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  id?: InputMaybe<Scalars["String"]>;
  provider: RelatedNodeInput;
  role: RelatedNodeInput;
  status: RelatedNodeInput;
  vendor_id?: InputMaybe<StringAttributeInput>;
};

export type CircuitDelete = {
  __typename?: "CircuitDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CircuitEndpoint = {
  __typename?: "CircuitEndpoint";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  circuit?: Maybe<RelatedCircuit>;
  connected_interface?: Maybe<RelatedInterface>;
  description?: Maybe<StrAttribute>;
  id: Scalars["String"];
  site?: Maybe<RelatedLocation>;
};

export type CircuitEndpointCreate = {
  __typename?: "CircuitEndpointCreate";
  object?: Maybe<CircuitEndpoint>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CircuitEndpointCreateInput = {
  circuit: RelatedNodeInput;
  connected_interface?: InputMaybe<RelatedNodeInput>;
  description?: InputMaybe<StringAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  site: RelatedNodeInput;
};

export type CircuitEndpointDelete = {
  __typename?: "CircuitEndpointDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CircuitEndpointUpdate = {
  __typename?: "CircuitEndpointUpdate";
  object?: Maybe<CircuitEndpoint>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CircuitEndpointUpdateInput = {
  circuit?: InputMaybe<RelatedNodeInput>;
  connected_interface?: InputMaybe<RelatedNodeInput>;
  description?: InputMaybe<StringAttributeInput>;
  id: Scalars["String"];
  site?: InputMaybe<RelatedNodeInput>;
};

export type CircuitUpdate = {
  __typename?: "CircuitUpdate";
  object?: Maybe<Circuit>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CircuitUpdateInput = {
  circuit_id?: InputMaybe<StringAttributeInput>;
  description?: InputMaybe<StringAttributeInput>;
  endpoints?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  id: Scalars["String"];
  provider?: InputMaybe<RelatedNodeInput>;
  role?: InputMaybe<RelatedNodeInput>;
  status?: InputMaybe<RelatedNodeInput>;
  vendor_id?: InputMaybe<StringAttributeInput>;
};

export type Criticality = {
  __typename?: "Criticality";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  description?: Maybe<StrAttribute>;
  id: Scalars["String"];
  level: IntAttribute;
  name: StrAttribute;
};

export type CriticalityCreate = {
  __typename?: "CriticalityCreate";
  object?: Maybe<Criticality>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CriticalityCreateInput = {
  description?: InputMaybe<StringAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  level: IntAttributeInput;
  name: StringAttributeInput;
};

export type CriticalityDelete = {
  __typename?: "CriticalityDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CriticalityUpdate = {
  __typename?: "CriticalityUpdate";
  object?: Maybe<Criticality>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CriticalityUpdateInput = {
  description?: InputMaybe<StringAttributeInput>;
  id: Scalars["String"];
  level?: InputMaybe<IntAttributeInput>;
  name?: InputMaybe<StringAttributeInput>;
};

export type DataOwner = {
  description?: Maybe<StrAttribute>;
  /** Unique identifier */
  id?: Maybe<Scalars["String"]>;
  name: StrAttribute;
};

/** Any Entities that stores or produces data. */
export type DataSource = {
  description?: Maybe<StrAttribute>;
  /** Unique identifier */
  id?: Maybe<Scalars["String"]>;
  name: StrAttribute;
};

export type DeleteInput = {
  id: Scalars["String"];
};

export type Device = {
  __typename?: "Device";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  asn?: Maybe<RelatedAutonomousSystem>;
  description?: Maybe<StrAttribute>;
  id: Scalars["String"];
  interfaces: Array<Maybe<RelatedInterface>>;
  name: StrAttribute;
  role?: Maybe<RelatedRole>;
  site?: Maybe<RelatedLocation>;
  status?: Maybe<RelatedStatus>;
  tags: Array<Maybe<RelatedTag>>;
  type: StrAttribute;
};

export type DeviceInterfacesArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  enabled__value?: InputMaybe<Scalars["Boolean"]>;
  id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  speed__value?: InputMaybe<Scalars["Int"]>;
};

export type DeviceTagsArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
};

export type DeviceCreate = {
  __typename?: "DeviceCreate";
  object?: Maybe<Device>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type DeviceCreateInput = {
  asn?: InputMaybe<RelatedNodeInput>;
  description?: InputMaybe<StringAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  interfaces?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name: StringAttributeInput;
  role: RelatedNodeInput;
  site: RelatedNodeInput;
  status: RelatedNodeInput;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  type: StringAttributeInput;
};

export type DeviceDelete = {
  __typename?: "DeviceDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

export type DeviceUpdate = {
  __typename?: "DeviceUpdate";
  object?: Maybe<Device>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type DeviceUpdateInput = {
  asn?: InputMaybe<RelatedNodeInput>;
  description?: InputMaybe<StringAttributeInput>;
  id: Scalars["String"];
  interfaces?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name?: InputMaybe<StringAttributeInput>;
  role?: InputMaybe<RelatedNodeInput>;
  site?: InputMaybe<RelatedNodeInput>;
  status?: InputMaybe<RelatedNodeInput>;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  type?: InputMaybe<StringAttributeInput>;
};

export type GenericSchema = {
  __typename?: "GenericSchema";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  attributes: Array<Maybe<RelatedAttributeSchema>>;
  description?: Maybe<StrAttribute>;
  id: Scalars["String"];
  kind: StrAttribute;
  label?: Maybe<StrAttribute>;
  name: StrAttribute;
  relationships: Array<Maybe<RelatedRelationshipSchema>>;
};

export type GenericSchemaAttributesArgs = {
  branch__value?: InputMaybe<Scalars["Boolean"]>;
  default_value__value?: InputMaybe<Scalars["GenericScalar"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
  inherited__value?: InputMaybe<Scalars["Boolean"]>;
  kind__value?: InputMaybe<Scalars["String"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  optional__value?: InputMaybe<Scalars["Boolean"]>;
  unique__value?: InputMaybe<Scalars["Boolean"]>;
};

export type GenericSchemaRelationshipsArgs = {
  branch__value?: InputMaybe<Scalars["Boolean"]>;
  cardinality__value?: InputMaybe<Scalars["String"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
  identifier__value?: InputMaybe<Scalars["String"]>;
  inherited__value?: InputMaybe<Scalars["Boolean"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  optional__value?: InputMaybe<Scalars["Boolean"]>;
  peer__value?: InputMaybe<Scalars["String"]>;
};

export type GenericSchemaCreate = {
  __typename?: "GenericSchemaCreate";
  object?: Maybe<GenericSchema>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type GenericSchemaCreateInput = {
  attributes?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  description?: InputMaybe<StringAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  kind: StringAttributeInput;
  label?: InputMaybe<StringAttributeInput>;
  name: StringAttributeInput;
  relationships?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

export type GenericSchemaDelete = {
  __typename?: "GenericSchemaDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

export type GenericSchemaUpdate = {
  __typename?: "GenericSchemaUpdate";
  object?: Maybe<GenericSchema>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type GenericSchemaUpdateInput = {
  attributes?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  description?: InputMaybe<StringAttributeInput>;
  id: Scalars["String"];
  kind?: InputMaybe<StringAttributeInput>;
  label?: InputMaybe<StringAttributeInput>;
  name?: InputMaybe<StringAttributeInput>;
  relationships?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

export type GraphQlQuery = {
  __typename?: "GraphQLQuery";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  description?: Maybe<StrAttribute>;
  id: Scalars["String"];
  name: StrAttribute;
  query: StrAttribute;
  tags: Array<Maybe<RelatedTag>>;
};

export type GraphQlQueryTagsArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
};

export type GraphQlQueryCreate = {
  __typename?: "GraphQLQueryCreate";
  object?: Maybe<GraphQlQuery>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type GraphQlQueryCreateInput = {
  description?: InputMaybe<StringAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  name: StringAttributeInput;
  query: StringAttributeInput;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

export type GraphQlQueryDelete = {
  __typename?: "GraphQLQueryDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

export type GraphQlQueryUpdate = {
  __typename?: "GraphQLQueryUpdate";
  object?: Maybe<GraphQlQuery>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type GraphQlQueryUpdateInput = {
  description?: InputMaybe<StringAttributeInput>;
  id: Scalars["String"];
  name?: InputMaybe<StringAttributeInput>;
  query?: InputMaybe<StringAttributeInput>;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

export type Group = DataOwner & {
  __typename?: "Group";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  description?: Maybe<StrAttribute>;
  id: Scalars["String"];
  members: Array<Maybe<RelatedAccount>>;
  name: StrAttribute;
};

export type GroupMembersArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  type__value?: InputMaybe<Scalars["String"]>;
};

export type GroupCreate = {
  __typename?: "GroupCreate";
  object?: Maybe<Group>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type GroupCreateInput = {
  description?: InputMaybe<StringAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  members?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name: StringAttributeInput;
};

export type GroupDelete = {
  __typename?: "GroupDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

export type GroupSchema = {
  __typename?: "GroupSchema";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  description?: Maybe<StrAttribute>;
  id: Scalars["String"];
  kind: StrAttribute;
  name: StrAttribute;
};

export type GroupSchemaCreate = {
  __typename?: "GroupSchemaCreate";
  object?: Maybe<GroupSchema>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type GroupSchemaCreateInput = {
  description?: InputMaybe<StringAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  kind: StringAttributeInput;
  name: StringAttributeInput;
};

export type GroupSchemaDelete = {
  __typename?: "GroupSchemaDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

export type GroupSchemaUpdate = {
  __typename?: "GroupSchemaUpdate";
  object?: Maybe<GroupSchema>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type GroupSchemaUpdateInput = {
  description?: InputMaybe<StringAttributeInput>;
  id: Scalars["String"];
  kind?: InputMaybe<StringAttributeInput>;
  name?: InputMaybe<StringAttributeInput>;
};

export type GroupUpdate = {
  __typename?: "GroupUpdate";
  object?: Maybe<Group>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type GroupUpdateInput = {
  description?: InputMaybe<StringAttributeInput>;
  id: Scalars["String"];
  members?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name?: InputMaybe<StringAttributeInput>;
};

export type IpAddress = {
  __typename?: "IPAddress";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  address: StrAttribute;
  description?: Maybe<StrAttribute>;
  id: Scalars["String"];
  interface?: Maybe<RelatedInterface>;
};

export type IpAddressCreate = {
  __typename?: "IPAddressCreate";
  object?: Maybe<IpAddress>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type IpAddressCreateInput = {
  address: StringAttributeInput;
  description?: InputMaybe<StringAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  interface?: InputMaybe<RelatedNodeInput>;
};

export type IpAddressDelete = {
  __typename?: "IPAddressDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

export type IpAddressUpdate = {
  __typename?: "IPAddressUpdate";
  object?: Maybe<IpAddress>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type IpAddressUpdateInput = {
  address?: InputMaybe<StringAttributeInput>;
  description?: InputMaybe<StringAttributeInput>;
  id: Scalars["String"];
  interface?: InputMaybe<RelatedNodeInput>;
};

/** Attribute of type Integer */
export type IntAttribute = AttributeInterface & {
  __typename?: "IntAttribute";
  id?: Maybe<Scalars["String"]>;
  is_inherited?: Maybe<Scalars["Boolean"]>;
  is_protected?: Maybe<Scalars["Boolean"]>;
  is_visible?: Maybe<Scalars["Boolean"]>;
  owner?: Maybe<DataOwner>;
  source?: Maybe<DataSource>;
  updated_at?: Maybe<Scalars["DateTime"]>;
  value?: Maybe<Scalars["Int"]>;
};

export type IntAttributeInput = {
  is_protected?: InputMaybe<Scalars["Boolean"]>;
  is_visible?: InputMaybe<Scalars["Boolean"]>;
  owner?: InputMaybe<Scalars["String"]>;
  source?: InputMaybe<Scalars["String"]>;
  value?: InputMaybe<Scalars["Int"]>;
};

export type Interface = {
  __typename?: "Interface";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  connected_circuit?: Maybe<RelatedCircuitEndpoint>;
  connected_interface?: Maybe<RelatedInterface>;
  description?: Maybe<StrAttribute>;
  device?: Maybe<RelatedDevice>;
  enabled: BoolAttribute;
  id: Scalars["String"];
  ip_addresses: Array<Maybe<RelatedIpAddress>>;
  name: StrAttribute;
  role?: Maybe<RelatedRole>;
  speed: IntAttribute;
  status?: Maybe<RelatedStatus>;
  tags: Array<Maybe<RelatedTag>>;
};

export type InterfaceIp_AddressesArgs = {
  address__value?: InputMaybe<Scalars["String"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
};

export type InterfaceTagsArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
};

export type InterfaceCreate = {
  __typename?: "InterfaceCreate";
  object?: Maybe<Interface>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type InterfaceCreateInput = {
  connected_circuit?: InputMaybe<RelatedNodeInput>;
  connected_interface?: InputMaybe<RelatedNodeInput>;
  description?: InputMaybe<StringAttributeInput>;
  device: RelatedNodeInput;
  enabled?: InputMaybe<BoolAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  ip_addresses?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name: StringAttributeInput;
  role: RelatedNodeInput;
  speed: IntAttributeInput;
  status: RelatedNodeInput;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

export type InterfaceDelete = {
  __typename?: "InterfaceDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

export type InterfaceUpdate = {
  __typename?: "InterfaceUpdate";
  object?: Maybe<Interface>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type InterfaceUpdateInput = {
  connected_circuit?: InputMaybe<RelatedNodeInput>;
  connected_interface?: InputMaybe<RelatedNodeInput>;
  description?: InputMaybe<StringAttributeInput>;
  device?: InputMaybe<RelatedNodeInput>;
  enabled?: InputMaybe<BoolAttributeInput>;
  id: Scalars["String"];
  ip_addresses?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name?: InputMaybe<StringAttributeInput>;
  role?: InputMaybe<RelatedNodeInput>;
  speed?: InputMaybe<IntAttributeInput>;
  status?: InputMaybe<RelatedNodeInput>;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** Attribute of type List */
export type ListAttribute = AttributeInterface & {
  __typename?: "ListAttribute";
  id?: Maybe<Scalars["String"]>;
  is_inherited?: Maybe<Scalars["Boolean"]>;
  is_protected?: Maybe<Scalars["Boolean"]>;
  is_visible?: Maybe<Scalars["Boolean"]>;
  owner?: Maybe<DataOwner>;
  source?: Maybe<DataSource>;
  updated_at?: Maybe<Scalars["DateTime"]>;
  value?: Maybe<Scalars["GenericScalar"]>;
};

export type ListAttributeInput = {
  is_protected?: InputMaybe<Scalars["Boolean"]>;
  is_visible?: InputMaybe<Scalars["Boolean"]>;
  owner?: InputMaybe<Scalars["String"]>;
  source?: InputMaybe<Scalars["String"]>;
  value?: InputMaybe<Scalars["GenericScalar"]>;
};

export type Location = {
  __typename?: "Location";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  description?: Maybe<StrAttribute>;
  id: Scalars["String"];
  name: StrAttribute;
  tags: Array<Maybe<RelatedTag>>;
  type: StrAttribute;
};

export type LocationTagsArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
};

export type LocationCreate = {
  __typename?: "LocationCreate";
  object?: Maybe<Location>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type LocationCreateInput = {
  description?: InputMaybe<StringAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  name: StringAttributeInput;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  type: StringAttributeInput;
};

export type LocationDelete = {
  __typename?: "LocationDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

export type LocationUpdate = {
  __typename?: "LocationUpdate";
  object?: Maybe<Location>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type LocationUpdateInput = {
  description?: InputMaybe<StringAttributeInput>;
  id: Scalars["String"];
  name?: InputMaybe<StringAttributeInput>;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  type?: InputMaybe<StringAttributeInput>;
};

export type Mutation = {
  __typename?: "Mutation";
  account_create?: Maybe<AccountCreate>;
  account_delete?: Maybe<AccountDelete>;
  account_token_create?: Maybe<AccountTokenCreate>;
  account_token_delete?: Maybe<AccountTokenDelete>;
  account_token_update?: Maybe<AccountTokenUpdate>;
  account_update?: Maybe<AccountUpdate>;
  attribute_schema_create?: Maybe<AttributeSchemaCreate>;
  attribute_schema_delete?: Maybe<AttributeSchemaDelete>;
  attribute_schema_update?: Maybe<AttributeSchemaUpdate>;
  autonomous_system_create?: Maybe<AutonomousSystemCreate>;
  autonomous_system_delete?: Maybe<AutonomousSystemDelete>;
  autonomous_system_update?: Maybe<AutonomousSystemUpdate>;
  bgp_peer_group_create?: Maybe<BgpPeerGroupCreate>;
  bgp_peer_group_delete?: Maybe<BgpPeerGroupDelete>;
  bgp_peer_group_update?: Maybe<BgpPeerGroupUpdate>;
  bgp_session_create?: Maybe<BgpSessionCreate>;
  bgp_session_delete?: Maybe<BgpSessionDelete>;
  bgp_session_update?: Maybe<BgpSessionUpdate>;
  branch_create?: Maybe<BranchCreate>;
  branch_merge?: Maybe<BranchMerge>;
  branch_rebase?: Maybe<BranchRebase>;
  branch_validate?: Maybe<BranchValidate>;
  check_create?: Maybe<CheckCreate>;
  check_delete?: Maybe<CheckDelete>;
  check_update?: Maybe<CheckUpdate>;
  circuit_create?: Maybe<CircuitCreate>;
  circuit_delete?: Maybe<CircuitDelete>;
  circuit_endpoint_create?: Maybe<CircuitEndpointCreate>;
  circuit_endpoint_delete?: Maybe<CircuitEndpointDelete>;
  circuit_endpoint_update?: Maybe<CircuitEndpointUpdate>;
  circuit_update?: Maybe<CircuitUpdate>;
  criticality_create?: Maybe<CriticalityCreate>;
  criticality_delete?: Maybe<CriticalityDelete>;
  criticality_update?: Maybe<CriticalityUpdate>;
  device_create?: Maybe<DeviceCreate>;
  device_delete?: Maybe<DeviceDelete>;
  device_update?: Maybe<DeviceUpdate>;
  generic_schema_create?: Maybe<GenericSchemaCreate>;
  generic_schema_delete?: Maybe<GenericSchemaDelete>;
  generic_schema_update?: Maybe<GenericSchemaUpdate>;
  graphql_query_create?: Maybe<GraphQlQueryCreate>;
  graphql_query_delete?: Maybe<GraphQlQueryDelete>;
  graphql_query_update?: Maybe<GraphQlQueryUpdate>;
  group_create?: Maybe<GroupCreate>;
  group_delete?: Maybe<GroupDelete>;
  group_schema_create?: Maybe<GroupSchemaCreate>;
  group_schema_delete?: Maybe<GroupSchemaDelete>;
  group_schema_update?: Maybe<GroupSchemaUpdate>;
  group_update?: Maybe<GroupUpdate>;
  interface_create?: Maybe<InterfaceCreate>;
  interface_delete?: Maybe<InterfaceDelete>;
  interface_update?: Maybe<InterfaceUpdate>;
  ipaddress_create?: Maybe<IpAddressCreate>;
  ipaddress_delete?: Maybe<IpAddressDelete>;
  ipaddress_update?: Maybe<IpAddressUpdate>;
  location_create?: Maybe<LocationCreate>;
  location_delete?: Maybe<LocationDelete>;
  location_update?: Maybe<LocationUpdate>;
  node_schema_create?: Maybe<NodeSchemaCreate>;
  node_schema_delete?: Maybe<NodeSchemaDelete>;
  node_schema_update?: Maybe<NodeSchemaUpdate>;
  organization_create?: Maybe<OrganizationCreate>;
  organization_delete?: Maybe<OrganizationDelete>;
  organization_update?: Maybe<OrganizationUpdate>;
  relationship_schema_create?: Maybe<RelationshipSchemaCreate>;
  relationship_schema_delete?: Maybe<RelationshipSchemaDelete>;
  relationship_schema_update?: Maybe<RelationshipSchemaUpdate>;
  repository_create?: Maybe<RepositoryCreate>;
  repository_delete?: Maybe<RepositoryDelete>;
  repository_update?: Maybe<RepositoryUpdate>;
  rfile_create?: Maybe<RFileCreate>;
  rfile_delete?: Maybe<RFileDelete>;
  rfile_update?: Maybe<RFileUpdate>;
  role_create?: Maybe<RoleCreate>;
  role_delete?: Maybe<RoleDelete>;
  role_update?: Maybe<RoleUpdate>;
  status_create?: Maybe<StatusCreate>;
  status_delete?: Maybe<StatusDelete>;
  status_update?: Maybe<StatusUpdate>;
  tag_create?: Maybe<TagCreate>;
  tag_delete?: Maybe<TagDelete>;
  tag_update?: Maybe<TagUpdate>;
  transform_python_create?: Maybe<TransformPythonCreate>;
  transform_python_delete?: Maybe<TransformPythonDelete>;
  transform_python_update?: Maybe<TransformPythonUpdate>;
};

export type MutationAccount_CreateArgs = {
  data: AccountCreateInput;
};

export type MutationAccount_DeleteArgs = {
  data: DeleteInput;
};

export type MutationAccount_Token_CreateArgs = {
  data: AccountTokenCreateInput;
};

export type MutationAccount_Token_DeleteArgs = {
  data: DeleteInput;
};

export type MutationAccount_Token_UpdateArgs = {
  data: AccountTokenUpdateInput;
};

export type MutationAccount_UpdateArgs = {
  data: AccountUpdateInput;
};

export type MutationAttribute_Schema_CreateArgs = {
  data: AttributeSchemaCreateInput;
};

export type MutationAttribute_Schema_DeleteArgs = {
  data: DeleteInput;
};

export type MutationAttribute_Schema_UpdateArgs = {
  data: AttributeSchemaUpdateInput;
};

export type MutationAutonomous_System_CreateArgs = {
  data: AutonomousSystemCreateInput;
};

export type MutationAutonomous_System_DeleteArgs = {
  data: DeleteInput;
};

export type MutationAutonomous_System_UpdateArgs = {
  data: AutonomousSystemUpdateInput;
};

export type MutationBgp_Peer_Group_CreateArgs = {
  data: BgpPeerGroupCreateInput;
};

export type MutationBgp_Peer_Group_DeleteArgs = {
  data: DeleteInput;
};

export type MutationBgp_Peer_Group_UpdateArgs = {
  data: BgpPeerGroupUpdateInput;
};

export type MutationBgp_Session_CreateArgs = {
  data: BgpSessionCreateInput;
};

export type MutationBgp_Session_DeleteArgs = {
  data: DeleteInput;
};

export type MutationBgp_Session_UpdateArgs = {
  data: BgpSessionUpdateInput;
};

export type MutationBranch_CreateArgs = {
  background_execution?: InputMaybe<Scalars["Boolean"]>;
  data: BranchCreateInput;
};

export type MutationBranch_MergeArgs = {
  data: BranchNameInput;
};

export type MutationBranch_RebaseArgs = {
  data: BranchNameInput;
};

export type MutationBranch_ValidateArgs = {
  data: BranchNameInput;
};

export type MutationCheck_CreateArgs = {
  data: CheckCreateInput;
};

export type MutationCheck_DeleteArgs = {
  data: DeleteInput;
};

export type MutationCheck_UpdateArgs = {
  data: CheckUpdateInput;
};

export type MutationCircuit_CreateArgs = {
  data: CircuitCreateInput;
};

export type MutationCircuit_DeleteArgs = {
  data: DeleteInput;
};

export type MutationCircuit_Endpoint_CreateArgs = {
  data: CircuitEndpointCreateInput;
};

export type MutationCircuit_Endpoint_DeleteArgs = {
  data: DeleteInput;
};

export type MutationCircuit_Endpoint_UpdateArgs = {
  data: CircuitEndpointUpdateInput;
};

export type MutationCircuit_UpdateArgs = {
  data: CircuitUpdateInput;
};

export type MutationCriticality_CreateArgs = {
  data: CriticalityCreateInput;
};

export type MutationCriticality_DeleteArgs = {
  data: DeleteInput;
};

export type MutationCriticality_UpdateArgs = {
  data: CriticalityUpdateInput;
};

export type MutationDevice_CreateArgs = {
  data: DeviceCreateInput;
};

export type MutationDevice_DeleteArgs = {
  data: DeleteInput;
};

export type MutationDevice_UpdateArgs = {
  data: DeviceUpdateInput;
};

export type MutationGeneric_Schema_CreateArgs = {
  data: GenericSchemaCreateInput;
};

export type MutationGeneric_Schema_DeleteArgs = {
  data: DeleteInput;
};

export type MutationGeneric_Schema_UpdateArgs = {
  data: GenericSchemaUpdateInput;
};

export type MutationGraphql_Query_CreateArgs = {
  data: GraphQlQueryCreateInput;
};

export type MutationGraphql_Query_DeleteArgs = {
  data: DeleteInput;
};

export type MutationGraphql_Query_UpdateArgs = {
  data: GraphQlQueryUpdateInput;
};

export type MutationGroup_CreateArgs = {
  data: GroupCreateInput;
};

export type MutationGroup_DeleteArgs = {
  data: DeleteInput;
};

export type MutationGroup_Schema_CreateArgs = {
  data: GroupSchemaCreateInput;
};

export type MutationGroup_Schema_DeleteArgs = {
  data: DeleteInput;
};

export type MutationGroup_Schema_UpdateArgs = {
  data: GroupSchemaUpdateInput;
};

export type MutationGroup_UpdateArgs = {
  data: GroupUpdateInput;
};

export type MutationInterface_CreateArgs = {
  data: InterfaceCreateInput;
};

export type MutationInterface_DeleteArgs = {
  data: DeleteInput;
};

export type MutationInterface_UpdateArgs = {
  data: InterfaceUpdateInput;
};

export type MutationIpaddress_CreateArgs = {
  data: IpAddressCreateInput;
};

export type MutationIpaddress_DeleteArgs = {
  data: DeleteInput;
};

export type MutationIpaddress_UpdateArgs = {
  data: IpAddressUpdateInput;
};

export type MutationLocation_CreateArgs = {
  data: LocationCreateInput;
};

export type MutationLocation_DeleteArgs = {
  data: DeleteInput;
};

export type MutationLocation_UpdateArgs = {
  data: LocationUpdateInput;
};

export type MutationNode_Schema_CreateArgs = {
  data: NodeSchemaCreateInput;
};

export type MutationNode_Schema_DeleteArgs = {
  data: DeleteInput;
};

export type MutationNode_Schema_UpdateArgs = {
  data: NodeSchemaUpdateInput;
};

export type MutationOrganization_CreateArgs = {
  data: OrganizationCreateInput;
};

export type MutationOrganization_DeleteArgs = {
  data: DeleteInput;
};

export type MutationOrganization_UpdateArgs = {
  data: OrganizationUpdateInput;
};

export type MutationRelationship_Schema_CreateArgs = {
  data: RelationshipSchemaCreateInput;
};

export type MutationRelationship_Schema_DeleteArgs = {
  data: DeleteInput;
};

export type MutationRelationship_Schema_UpdateArgs = {
  data: RelationshipSchemaUpdateInput;
};

export type MutationRepository_CreateArgs = {
  data: RepositoryCreateInput;
};

export type MutationRepository_DeleteArgs = {
  data: DeleteInput;
};

export type MutationRepository_UpdateArgs = {
  data: RepositoryUpdateInput;
};

export type MutationRfile_CreateArgs = {
  data: RFileCreateInput;
};

export type MutationRfile_DeleteArgs = {
  data: DeleteInput;
};

export type MutationRfile_UpdateArgs = {
  data: RFileUpdateInput;
};

export type MutationRole_CreateArgs = {
  data: RoleCreateInput;
};

export type MutationRole_DeleteArgs = {
  data: DeleteInput;
};

export type MutationRole_UpdateArgs = {
  data: RoleUpdateInput;
};

export type MutationStatus_CreateArgs = {
  data: StatusCreateInput;
};

export type MutationStatus_DeleteArgs = {
  data: DeleteInput;
};

export type MutationStatus_UpdateArgs = {
  data: StatusUpdateInput;
};

export type MutationTag_CreateArgs = {
  data: TagCreateInput;
};

export type MutationTag_DeleteArgs = {
  data: DeleteInput;
};

export type MutationTag_UpdateArgs = {
  data: TagUpdateInput;
};

export type MutationTransform_Python_CreateArgs = {
  data: TransformPythonCreateInput;
};

export type MutationTransform_Python_DeleteArgs = {
  data: DeleteInput;
};

export type MutationTransform_Python_UpdateArgs = {
  data: TransformPythonUpdateInput;
};

export type NodeSchema = {
  __typename?: "NodeSchema";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  attributes: Array<Maybe<RelatedAttributeSchema>>;
  branch: BoolAttribute;
  default_filter?: Maybe<StrAttribute>;
  description?: Maybe<StrAttribute>;
  groups: ListAttribute;
  id: Scalars["String"];
  inherit_from: ListAttribute;
  kind: StrAttribute;
  label?: Maybe<StrAttribute>;
  name: StrAttribute;
  relationships: Array<Maybe<RelatedRelationshipSchema>>;
};

export type NodeSchemaAttributesArgs = {
  branch__value?: InputMaybe<Scalars["Boolean"]>;
  default_value__value?: InputMaybe<Scalars["GenericScalar"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
  inherited__value?: InputMaybe<Scalars["Boolean"]>;
  kind__value?: InputMaybe<Scalars["String"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  optional__value?: InputMaybe<Scalars["Boolean"]>;
  unique__value?: InputMaybe<Scalars["Boolean"]>;
};

export type NodeSchemaRelationshipsArgs = {
  branch__value?: InputMaybe<Scalars["Boolean"]>;
  cardinality__value?: InputMaybe<Scalars["String"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
  identifier__value?: InputMaybe<Scalars["String"]>;
  inherited__value?: InputMaybe<Scalars["Boolean"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  optional__value?: InputMaybe<Scalars["Boolean"]>;
  peer__value?: InputMaybe<Scalars["String"]>;
};

export type NodeSchemaCreate = {
  __typename?: "NodeSchemaCreate";
  object?: Maybe<NodeSchema>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type NodeSchemaCreateInput = {
  attributes?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  branch: BoolAttributeInput;
  default_filter?: InputMaybe<StringAttributeInput>;
  description?: InputMaybe<StringAttributeInput>;
  groups: ListAttributeInput;
  id?: InputMaybe<Scalars["String"]>;
  inherit_from: ListAttributeInput;
  kind: StringAttributeInput;
  label?: InputMaybe<StringAttributeInput>;
  name: StringAttributeInput;
  relationships?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

export type NodeSchemaDelete = {
  __typename?: "NodeSchemaDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

export type NodeSchemaUpdate = {
  __typename?: "NodeSchemaUpdate";
  object?: Maybe<NodeSchema>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type NodeSchemaUpdateInput = {
  attributes?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  branch?: InputMaybe<BoolAttributeInput>;
  default_filter?: InputMaybe<StringAttributeInput>;
  description?: InputMaybe<StringAttributeInput>;
  groups?: InputMaybe<ListAttributeInput>;
  id: Scalars["String"];
  inherit_from?: InputMaybe<ListAttributeInput>;
  kind?: InputMaybe<StringAttributeInput>;
  label?: InputMaybe<StringAttributeInput>;
  name?: InputMaybe<StringAttributeInput>;
  relationships?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

export type Organization = {
  __typename?: "Organization";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  description?: Maybe<StrAttribute>;
  id: Scalars["String"];
  name: StrAttribute;
  tags: Array<Maybe<RelatedTag>>;
};

export type OrganizationTagsArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
};

export type OrganizationCreate = {
  __typename?: "OrganizationCreate";
  object?: Maybe<Organization>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type OrganizationCreateInput = {
  description?: InputMaybe<StringAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  name: StringAttributeInput;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

export type OrganizationDelete = {
  __typename?: "OrganizationDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

export type OrganizationUpdate = {
  __typename?: "OrganizationUpdate";
  object?: Maybe<Organization>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type OrganizationUpdateInput = {
  description?: InputMaybe<StringAttributeInput>;
  id: Scalars["String"];
  name?: InputMaybe<StringAttributeInput>;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

export type Query = {
  __typename?: "Query";
  account?: Maybe<Array<Maybe<Account>>>;
  account_token?: Maybe<Array<Maybe<AccountToken>>>;
  attribute_schema?: Maybe<Array<Maybe<AttributeSchema>>>;
  autonomous_system?: Maybe<Array<Maybe<AutonomousSystem>>>;
  bgp_peer_group?: Maybe<Array<Maybe<BgpPeerGroup>>>;
  bgp_session?: Maybe<Array<Maybe<BgpSession>>>;
  branch?: Maybe<Array<Maybe<Branch>>>;
  check?: Maybe<Array<Maybe<Check>>>;
  circuit?: Maybe<Array<Maybe<Circuit>>>;
  circuit_endpoint?: Maybe<Array<Maybe<CircuitEndpoint>>>;
  criticality?: Maybe<Array<Maybe<Criticality>>>;
  device?: Maybe<Array<Maybe<Device>>>;
  diff?: Maybe<BranchDiffType>;
  generic_schema?: Maybe<Array<Maybe<GenericSchema>>>;
  graphql_query?: Maybe<Array<Maybe<GraphQlQuery>>>;
  group?: Maybe<Array<Maybe<Group>>>;
  group_schema?: Maybe<Array<Maybe<GroupSchema>>>;
  interface?: Maybe<Array<Maybe<Interface>>>;
  ipaddress?: Maybe<Array<Maybe<IpAddress>>>;
  location?: Maybe<Array<Maybe<Location>>>;
  node_schema?: Maybe<Array<Maybe<NodeSchema>>>;
  organization?: Maybe<Array<Maybe<Organization>>>;
  relationship_schema?: Maybe<Array<Maybe<RelationshipSchema>>>;
  repository?: Maybe<Array<Maybe<Repository>>>;
  rfile?: Maybe<Array<Maybe<RFile>>>;
  role?: Maybe<Array<Maybe<Role>>>;
  status?: Maybe<Array<Maybe<Status>>>;
  tag?: Maybe<Array<Maybe<Tag>>>;
  transform_python?: Maybe<Array<Maybe<TransformPython>>>;
};

export type QueryAccountArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  groups__description__value?: InputMaybe<Scalars["String"]>;
  groups__id?: InputMaybe<Scalars["ID"]>;
  groups__name__value?: InputMaybe<Scalars["String"]>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  name__value?: InputMaybe<Scalars["String"]>;
  tokens__expiration_date__value?: InputMaybe<Scalars["String"]>;
  tokens__id?: InputMaybe<Scalars["ID"]>;
  tokens__token__value?: InputMaybe<Scalars["String"]>;
  type__value?: InputMaybe<Scalars["String"]>;
};

export type QueryAccount_TokenArgs = {
  account__description__value?: InputMaybe<Scalars["String"]>;
  account__id?: InputMaybe<Scalars["ID"]>;
  account__name__value?: InputMaybe<Scalars["String"]>;
  account__type__value?: InputMaybe<Scalars["String"]>;
  expiration_date__value?: InputMaybe<Scalars["String"]>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  token__value?: InputMaybe<Scalars["String"]>;
};

export type QueryAttribute_SchemaArgs = {
  branch__value?: InputMaybe<Scalars["Boolean"]>;
  default_value__value?: InputMaybe<Scalars["GenericScalar"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  inherited__value?: InputMaybe<Scalars["Boolean"]>;
  kind__value?: InputMaybe<Scalars["String"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  optional__value?: InputMaybe<Scalars["Boolean"]>;
  unique__value?: InputMaybe<Scalars["Boolean"]>;
};

export type QueryAutonomous_SystemArgs = {
  asn__value?: InputMaybe<Scalars["Int"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  name__value?: InputMaybe<Scalars["String"]>;
  organization__description__value?: InputMaybe<Scalars["String"]>;
  organization__id?: InputMaybe<Scalars["ID"]>;
  organization__name__value?: InputMaybe<Scalars["String"]>;
};

export type QueryBgp_Peer_GroupArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  export_policies__value?: InputMaybe<Scalars["String"]>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  import_policies__value?: InputMaybe<Scalars["String"]>;
  local_as__asn__value?: InputMaybe<Scalars["Int"]>;
  local_as__description__value?: InputMaybe<Scalars["String"]>;
  local_as__id?: InputMaybe<Scalars["ID"]>;
  local_as__name__value?: InputMaybe<Scalars["String"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  remote_as__asn__value?: InputMaybe<Scalars["Int"]>;
  remote_as__description__value?: InputMaybe<Scalars["String"]>;
  remote_as__id?: InputMaybe<Scalars["ID"]>;
  remote_as__name__value?: InputMaybe<Scalars["String"]>;
};

export type QueryBgp_SessionArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  device__description__value?: InputMaybe<Scalars["String"]>;
  device__id?: InputMaybe<Scalars["ID"]>;
  device__name__value?: InputMaybe<Scalars["String"]>;
  device__type__value?: InputMaybe<Scalars["String"]>;
  export_policies__value?: InputMaybe<Scalars["String"]>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  import_policies__value?: InputMaybe<Scalars["String"]>;
  local_as__asn__value?: InputMaybe<Scalars["Int"]>;
  local_as__description__value?: InputMaybe<Scalars["String"]>;
  local_as__id?: InputMaybe<Scalars["ID"]>;
  local_as__name__value?: InputMaybe<Scalars["String"]>;
  local_ip__address__value?: InputMaybe<Scalars["String"]>;
  local_ip__description__value?: InputMaybe<Scalars["String"]>;
  local_ip__id?: InputMaybe<Scalars["ID"]>;
  peer_group__description__value?: InputMaybe<Scalars["String"]>;
  peer_group__export_policies__value?: InputMaybe<Scalars["String"]>;
  peer_group__id?: InputMaybe<Scalars["ID"]>;
  peer_group__import_policies__value?: InputMaybe<Scalars["String"]>;
  peer_group__name__value?: InputMaybe<Scalars["String"]>;
  peer_session__description__value?: InputMaybe<Scalars["String"]>;
  peer_session__export_policies__value?: InputMaybe<Scalars["String"]>;
  peer_session__id?: InputMaybe<Scalars["ID"]>;
  peer_session__import_policies__value?: InputMaybe<Scalars["String"]>;
  peer_session__type__value?: InputMaybe<Scalars["String"]>;
  remote_as__asn__value?: InputMaybe<Scalars["Int"]>;
  remote_as__description__value?: InputMaybe<Scalars["String"]>;
  remote_as__id?: InputMaybe<Scalars["ID"]>;
  remote_as__name__value?: InputMaybe<Scalars["String"]>;
  remote_ip__address__value?: InputMaybe<Scalars["String"]>;
  remote_ip__description__value?: InputMaybe<Scalars["String"]>;
  remote_ip__id?: InputMaybe<Scalars["ID"]>;
  role__description__value?: InputMaybe<Scalars["String"]>;
  role__id?: InputMaybe<Scalars["ID"]>;
  role__name__value?: InputMaybe<Scalars["String"]>;
  status__description__value?: InputMaybe<Scalars["String"]>;
  status__id?: InputMaybe<Scalars["ID"]>;
  status__name__value?: InputMaybe<Scalars["String"]>;
  type__value?: InputMaybe<Scalars["String"]>;
};

export type QueryCheckArgs = {
  class_name__value?: InputMaybe<Scalars["String"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  file_path__value?: InputMaybe<Scalars["String"]>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  name__value?: InputMaybe<Scalars["String"]>;
  query__description__value?: InputMaybe<Scalars["String"]>;
  query__id?: InputMaybe<Scalars["ID"]>;
  query__name__value?: InputMaybe<Scalars["String"]>;
  query__query__value?: InputMaybe<Scalars["String"]>;
  rebase__value?: InputMaybe<Scalars["Boolean"]>;
  repository__commit__value?: InputMaybe<Scalars["String"]>;
  repository__default_branch__value?: InputMaybe<Scalars["String"]>;
  repository__description__value?: InputMaybe<Scalars["String"]>;
  repository__id?: InputMaybe<Scalars["ID"]>;
  repository__location__value?: InputMaybe<Scalars["String"]>;
  repository__name__value?: InputMaybe<Scalars["String"]>;
  repository__password__value?: InputMaybe<Scalars["String"]>;
  repository__type__value?: InputMaybe<Scalars["String"]>;
  repository__username__value?: InputMaybe<Scalars["String"]>;
  tags__description__value?: InputMaybe<Scalars["String"]>;
  tags__id?: InputMaybe<Scalars["ID"]>;
  tags__name__value?: InputMaybe<Scalars["String"]>;
  timeout__value?: InputMaybe<Scalars["Int"]>;
};

export type QueryCircuitArgs = {
  circuit_id__value?: InputMaybe<Scalars["String"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  endpoints__description__value?: InputMaybe<Scalars["String"]>;
  endpoints__id?: InputMaybe<Scalars["ID"]>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  provider__description__value?: InputMaybe<Scalars["String"]>;
  provider__id?: InputMaybe<Scalars["ID"]>;
  provider__name__value?: InputMaybe<Scalars["String"]>;
  role__description__value?: InputMaybe<Scalars["String"]>;
  role__id?: InputMaybe<Scalars["ID"]>;
  role__name__value?: InputMaybe<Scalars["String"]>;
  status__description__value?: InputMaybe<Scalars["String"]>;
  status__id?: InputMaybe<Scalars["ID"]>;
  status__name__value?: InputMaybe<Scalars["String"]>;
  vendor_id__value?: InputMaybe<Scalars["String"]>;
};

export type QueryCircuit_EndpointArgs = {
  circuit__circuit_id__value?: InputMaybe<Scalars["String"]>;
  circuit__description__value?: InputMaybe<Scalars["String"]>;
  circuit__id?: InputMaybe<Scalars["ID"]>;
  circuit__vendor_id__value?: InputMaybe<Scalars["String"]>;
  connected_interface__description__value?: InputMaybe<Scalars["String"]>;
  connected_interface__enabled__value?: InputMaybe<Scalars["Boolean"]>;
  connected_interface__id?: InputMaybe<Scalars["ID"]>;
  connected_interface__name__value?: InputMaybe<Scalars["String"]>;
  connected_interface__speed__value?: InputMaybe<Scalars["Int"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  site__description__value?: InputMaybe<Scalars["String"]>;
  site__id?: InputMaybe<Scalars["ID"]>;
  site__name__value?: InputMaybe<Scalars["String"]>;
  site__type__value?: InputMaybe<Scalars["String"]>;
};

export type QueryCriticalityArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  level__value?: InputMaybe<Scalars["Int"]>;
  name__value?: InputMaybe<Scalars["String"]>;
};

export type QueryDeviceArgs = {
  asn__asn__value?: InputMaybe<Scalars["Int"]>;
  asn__description__value?: InputMaybe<Scalars["String"]>;
  asn__id?: InputMaybe<Scalars["ID"]>;
  asn__name__value?: InputMaybe<Scalars["String"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  interfaces__description__value?: InputMaybe<Scalars["String"]>;
  interfaces__enabled__value?: InputMaybe<Scalars["Boolean"]>;
  interfaces__id?: InputMaybe<Scalars["ID"]>;
  interfaces__name__value?: InputMaybe<Scalars["String"]>;
  interfaces__speed__value?: InputMaybe<Scalars["Int"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  role__description__value?: InputMaybe<Scalars["String"]>;
  role__id?: InputMaybe<Scalars["ID"]>;
  role__name__value?: InputMaybe<Scalars["String"]>;
  site__description__value?: InputMaybe<Scalars["String"]>;
  site__id?: InputMaybe<Scalars["ID"]>;
  site__name__value?: InputMaybe<Scalars["String"]>;
  site__type__value?: InputMaybe<Scalars["String"]>;
  status__description__value?: InputMaybe<Scalars["String"]>;
  status__id?: InputMaybe<Scalars["ID"]>;
  status__name__value?: InputMaybe<Scalars["String"]>;
  tags__description__value?: InputMaybe<Scalars["String"]>;
  tags__id?: InputMaybe<Scalars["ID"]>;
  tags__name__value?: InputMaybe<Scalars["String"]>;
  type__value?: InputMaybe<Scalars["String"]>;
};

export type QueryDiffArgs = {
  branch: Scalars["String"];
  branch_only?: InputMaybe<Scalars["Boolean"]>;
  time_from?: InputMaybe<Scalars["String"]>;
  time_to?: InputMaybe<Scalars["String"]>;
};

export type QueryGeneric_SchemaArgs = {
  attributes__branch__value?: InputMaybe<Scalars["Boolean"]>;
  attributes__default_value__value?: InputMaybe<Scalars["GenericScalar"]>;
  attributes__description__value?: InputMaybe<Scalars["String"]>;
  attributes__id?: InputMaybe<Scalars["ID"]>;
  attributes__inherited__value?: InputMaybe<Scalars["Boolean"]>;
  attributes__kind__value?: InputMaybe<Scalars["String"]>;
  attributes__label__value?: InputMaybe<Scalars["String"]>;
  attributes__name__value?: InputMaybe<Scalars["String"]>;
  attributes__optional__value?: InputMaybe<Scalars["Boolean"]>;
  attributes__unique__value?: InputMaybe<Scalars["Boolean"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  kind__value?: InputMaybe<Scalars["String"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  relationships__branch__value?: InputMaybe<Scalars["Boolean"]>;
  relationships__cardinality__value?: InputMaybe<Scalars["String"]>;
  relationships__description__value?: InputMaybe<Scalars["String"]>;
  relationships__id?: InputMaybe<Scalars["ID"]>;
  relationships__identifier__value?: InputMaybe<Scalars["String"]>;
  relationships__inherited__value?: InputMaybe<Scalars["Boolean"]>;
  relationships__label__value?: InputMaybe<Scalars["String"]>;
  relationships__name__value?: InputMaybe<Scalars["String"]>;
  relationships__optional__value?: InputMaybe<Scalars["Boolean"]>;
  relationships__peer__value?: InputMaybe<Scalars["String"]>;
};

export type QueryGraphql_QueryArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  name__value?: InputMaybe<Scalars["String"]>;
  query__value?: InputMaybe<Scalars["String"]>;
  tags__description__value?: InputMaybe<Scalars["String"]>;
  tags__id?: InputMaybe<Scalars["ID"]>;
  tags__name__value?: InputMaybe<Scalars["String"]>;
};

export type QueryGroupArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  members__description__value?: InputMaybe<Scalars["String"]>;
  members__id?: InputMaybe<Scalars["ID"]>;
  members__name__value?: InputMaybe<Scalars["String"]>;
  members__type__value?: InputMaybe<Scalars["String"]>;
  name__value?: InputMaybe<Scalars["String"]>;
};

export type QueryGroup_SchemaArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  kind__value?: InputMaybe<Scalars["String"]>;
  name__value?: InputMaybe<Scalars["String"]>;
};

export type QueryInterfaceArgs = {
  connected_circuit__description__value?: InputMaybe<Scalars["String"]>;
  connected_circuit__id?: InputMaybe<Scalars["ID"]>;
  connected_interface__description__value?: InputMaybe<Scalars["String"]>;
  connected_interface__enabled__value?: InputMaybe<Scalars["Boolean"]>;
  connected_interface__id?: InputMaybe<Scalars["ID"]>;
  connected_interface__name__value?: InputMaybe<Scalars["String"]>;
  connected_interface__speed__value?: InputMaybe<Scalars["Int"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  device__description__value?: InputMaybe<Scalars["String"]>;
  device__id?: InputMaybe<Scalars["ID"]>;
  device__name__value?: InputMaybe<Scalars["String"]>;
  device__type__value?: InputMaybe<Scalars["String"]>;
  enabled__value?: InputMaybe<Scalars["Boolean"]>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  ip_addresses__address__value?: InputMaybe<Scalars["String"]>;
  ip_addresses__description__value?: InputMaybe<Scalars["String"]>;
  ip_addresses__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  role__description__value?: InputMaybe<Scalars["String"]>;
  role__id?: InputMaybe<Scalars["ID"]>;
  role__name__value?: InputMaybe<Scalars["String"]>;
  speed__value?: InputMaybe<Scalars["Int"]>;
  status__description__value?: InputMaybe<Scalars["String"]>;
  status__id?: InputMaybe<Scalars["ID"]>;
  status__name__value?: InputMaybe<Scalars["String"]>;
  tags__description__value?: InputMaybe<Scalars["String"]>;
  tags__id?: InputMaybe<Scalars["ID"]>;
  tags__name__value?: InputMaybe<Scalars["String"]>;
};

export type QueryIpaddressArgs = {
  address__value?: InputMaybe<Scalars["String"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  interface__description__value?: InputMaybe<Scalars["String"]>;
  interface__enabled__value?: InputMaybe<Scalars["Boolean"]>;
  interface__id?: InputMaybe<Scalars["ID"]>;
  interface__name__value?: InputMaybe<Scalars["String"]>;
  interface__speed__value?: InputMaybe<Scalars["Int"]>;
};

export type QueryLocationArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  name__value?: InputMaybe<Scalars["String"]>;
  tags__description__value?: InputMaybe<Scalars["String"]>;
  tags__id?: InputMaybe<Scalars["ID"]>;
  tags__name__value?: InputMaybe<Scalars["String"]>;
  type__value?: InputMaybe<Scalars["String"]>;
};

export type QueryNode_SchemaArgs = {
  attributes__branch__value?: InputMaybe<Scalars["Boolean"]>;
  attributes__default_value__value?: InputMaybe<Scalars["GenericScalar"]>;
  attributes__description__value?: InputMaybe<Scalars["String"]>;
  attributes__id?: InputMaybe<Scalars["ID"]>;
  attributes__inherited__value?: InputMaybe<Scalars["Boolean"]>;
  attributes__kind__value?: InputMaybe<Scalars["String"]>;
  attributes__label__value?: InputMaybe<Scalars["String"]>;
  attributes__name__value?: InputMaybe<Scalars["String"]>;
  attributes__optional__value?: InputMaybe<Scalars["Boolean"]>;
  attributes__unique__value?: InputMaybe<Scalars["Boolean"]>;
  branch__value?: InputMaybe<Scalars["Boolean"]>;
  default_filter__value?: InputMaybe<Scalars["String"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  groups__value?: InputMaybe<Scalars["GenericScalar"]>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  inherit_from__value?: InputMaybe<Scalars["GenericScalar"]>;
  kind__value?: InputMaybe<Scalars["String"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  relationships__branch__value?: InputMaybe<Scalars["Boolean"]>;
  relationships__cardinality__value?: InputMaybe<Scalars["String"]>;
  relationships__description__value?: InputMaybe<Scalars["String"]>;
  relationships__id?: InputMaybe<Scalars["ID"]>;
  relationships__identifier__value?: InputMaybe<Scalars["String"]>;
  relationships__inherited__value?: InputMaybe<Scalars["Boolean"]>;
  relationships__label__value?: InputMaybe<Scalars["String"]>;
  relationships__name__value?: InputMaybe<Scalars["String"]>;
  relationships__optional__value?: InputMaybe<Scalars["Boolean"]>;
  relationships__peer__value?: InputMaybe<Scalars["String"]>;
};

export type QueryOrganizationArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  name__value?: InputMaybe<Scalars["String"]>;
  tags__description__value?: InputMaybe<Scalars["String"]>;
  tags__id?: InputMaybe<Scalars["ID"]>;
  tags__name__value?: InputMaybe<Scalars["String"]>;
};

export type QueryRelationship_SchemaArgs = {
  branch__value?: InputMaybe<Scalars["Boolean"]>;
  cardinality__value?: InputMaybe<Scalars["String"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  identifier__value?: InputMaybe<Scalars["String"]>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  inherited__value?: InputMaybe<Scalars["Boolean"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  optional__value?: InputMaybe<Scalars["Boolean"]>;
  peer__value?: InputMaybe<Scalars["String"]>;
};

export type QueryRepositoryArgs = {
  account__description__value?: InputMaybe<Scalars["String"]>;
  account__id?: InputMaybe<Scalars["ID"]>;
  account__name__value?: InputMaybe<Scalars["String"]>;
  account__type__value?: InputMaybe<Scalars["String"]>;
  checks__class_name__value?: InputMaybe<Scalars["String"]>;
  checks__description__value?: InputMaybe<Scalars["String"]>;
  checks__file_path__value?: InputMaybe<Scalars["String"]>;
  checks__id?: InputMaybe<Scalars["ID"]>;
  checks__name__value?: InputMaybe<Scalars["String"]>;
  checks__rebase__value?: InputMaybe<Scalars["Boolean"]>;
  checks__timeout__value?: InputMaybe<Scalars["Int"]>;
  commit__value?: InputMaybe<Scalars["String"]>;
  default_branch__value?: InputMaybe<Scalars["String"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  location__value?: InputMaybe<Scalars["String"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  password__value?: InputMaybe<Scalars["String"]>;
  queries__description__value?: InputMaybe<Scalars["String"]>;
  queries__id?: InputMaybe<Scalars["ID"]>;
  queries__name__value?: InputMaybe<Scalars["String"]>;
  queries__query__value?: InputMaybe<Scalars["String"]>;
  rfiles__description__value?: InputMaybe<Scalars["String"]>;
  rfiles__id?: InputMaybe<Scalars["ID"]>;
  rfiles__name__value?: InputMaybe<Scalars["String"]>;
  rfiles__template_path__value?: InputMaybe<Scalars["String"]>;
  tags__description__value?: InputMaybe<Scalars["String"]>;
  tags__id?: InputMaybe<Scalars["ID"]>;
  tags__name__value?: InputMaybe<Scalars["String"]>;
  transform_python__class_name__value?: InputMaybe<Scalars["String"]>;
  transform_python__description__value?: InputMaybe<Scalars["String"]>;
  transform_python__file_path__value?: InputMaybe<Scalars["String"]>;
  transform_python__id?: InputMaybe<Scalars["ID"]>;
  transform_python__name__value?: InputMaybe<Scalars["String"]>;
  transform_python__rebase__value?: InputMaybe<Scalars["Boolean"]>;
  transform_python__timeout__value?: InputMaybe<Scalars["Int"]>;
  transform_python__url__value?: InputMaybe<Scalars["String"]>;
  type__value?: InputMaybe<Scalars["String"]>;
  username__value?: InputMaybe<Scalars["String"]>;
};

export type QueryRfileArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  name__value?: InputMaybe<Scalars["String"]>;
  query__description__value?: InputMaybe<Scalars["String"]>;
  query__id?: InputMaybe<Scalars["ID"]>;
  query__name__value?: InputMaybe<Scalars["String"]>;
  query__query__value?: InputMaybe<Scalars["String"]>;
  tags__description__value?: InputMaybe<Scalars["String"]>;
  tags__id?: InputMaybe<Scalars["ID"]>;
  tags__name__value?: InputMaybe<Scalars["String"]>;
  template_path__value?: InputMaybe<Scalars["String"]>;
  template_repository__commit__value?: InputMaybe<Scalars["String"]>;
  template_repository__default_branch__value?: InputMaybe<Scalars["String"]>;
  template_repository__description__value?: InputMaybe<Scalars["String"]>;
  template_repository__id?: InputMaybe<Scalars["ID"]>;
  template_repository__location__value?: InputMaybe<Scalars["String"]>;
  template_repository__name__value?: InputMaybe<Scalars["String"]>;
  template_repository__password__value?: InputMaybe<Scalars["String"]>;
  template_repository__type__value?: InputMaybe<Scalars["String"]>;
  template_repository__username__value?: InputMaybe<Scalars["String"]>;
};

export type QueryRoleArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  name__value?: InputMaybe<Scalars["String"]>;
};

export type QueryStatusArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  name__value?: InputMaybe<Scalars["String"]>;
};

export type QueryTagArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  name__value?: InputMaybe<Scalars["String"]>;
};

export type QueryTransform_PythonArgs = {
  class_name__value?: InputMaybe<Scalars["String"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  file_path__value?: InputMaybe<Scalars["String"]>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  name__value?: InputMaybe<Scalars["String"]>;
  query__description__value?: InputMaybe<Scalars["String"]>;
  query__id?: InputMaybe<Scalars["ID"]>;
  query__name__value?: InputMaybe<Scalars["String"]>;
  query__query__value?: InputMaybe<Scalars["String"]>;
  rebase__value?: InputMaybe<Scalars["Boolean"]>;
  repository__commit__value?: InputMaybe<Scalars["String"]>;
  repository__default_branch__value?: InputMaybe<Scalars["String"]>;
  repository__description__value?: InputMaybe<Scalars["String"]>;
  repository__id?: InputMaybe<Scalars["ID"]>;
  repository__location__value?: InputMaybe<Scalars["String"]>;
  repository__name__value?: InputMaybe<Scalars["String"]>;
  repository__password__value?: InputMaybe<Scalars["String"]>;
  repository__type__value?: InputMaybe<Scalars["String"]>;
  repository__username__value?: InputMaybe<Scalars["String"]>;
  tags__description__value?: InputMaybe<Scalars["String"]>;
  tags__id?: InputMaybe<Scalars["ID"]>;
  tags__name__value?: InputMaybe<Scalars["String"]>;
  timeout__value?: InputMaybe<Scalars["Int"]>;
  url__value?: InputMaybe<Scalars["String"]>;
};

export type RFile = {
  __typename?: "RFile";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  description?: Maybe<StrAttribute>;
  id: Scalars["String"];
  name: StrAttribute;
  query?: Maybe<RelatedGraphQlQuery>;
  tags: Array<Maybe<RelatedTag>>;
  template_path: StrAttribute;
  template_repository?: Maybe<RelatedRepository>;
};

export type RFileTagsArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
};

export type RFileCreate = {
  __typename?: "RFileCreate";
  object?: Maybe<RFile>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type RFileCreateInput = {
  description?: InputMaybe<StringAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  name: StringAttributeInput;
  query: RelatedNodeInput;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  template_path: StringAttributeInput;
  template_repository: RelatedNodeInput;
};

export type RFileDelete = {
  __typename?: "RFileDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

export type RFileUpdate = {
  __typename?: "RFileUpdate";
  object?: Maybe<RFile>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type RFileUpdateInput = {
  description?: InputMaybe<StringAttributeInput>;
  id: Scalars["String"];
  name?: InputMaybe<StringAttributeInput>;
  query?: InputMaybe<RelatedNodeInput>;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  template_path?: InputMaybe<StringAttributeInput>;
  template_repository?: InputMaybe<RelatedNodeInput>;
};

export type RelatedAccount = RelatedDataOwner &
  RelatedDataSource &
  RelatedNodeInterface & {
    __typename?: "RelatedAccount";
    _relation__is_protected?: Maybe<Scalars["Boolean"]>;
    _relation__is_visible?: Maybe<Scalars["Boolean"]>;
    _relation__owner?: Maybe<DataOwner>;
    _relation__source?: Maybe<DataSource>;
    _relation__updated_at?: Maybe<Scalars["DateTime"]>;
    _updated_at?: Maybe<Scalars["DateTime"]>;
    description?: Maybe<StrAttribute>;
    groups: Array<Maybe<RelatedGroup>>;
    id: Scalars["String"];
    name: StrAttribute;
    tokens: Array<Maybe<RelatedAccountToken>>;
    type: StrAttribute;
  };

export type RelatedAccountGroupsArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
};

export type RelatedAccountTokensArgs = {
  expiration_date__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
  token__value?: InputMaybe<Scalars["String"]>;
};

export type RelatedAccountToken = RelatedNodeInterface & {
  __typename?: "RelatedAccountToken";
  _relation__is_protected?: Maybe<Scalars["Boolean"]>;
  _relation__is_visible?: Maybe<Scalars["Boolean"]>;
  _relation__owner?: Maybe<DataOwner>;
  _relation__source?: Maybe<DataSource>;
  _relation__updated_at?: Maybe<Scalars["DateTime"]>;
  _updated_at?: Maybe<Scalars["DateTime"]>;
  account?: Maybe<RelatedAccount>;
  expiration_date?: Maybe<StrAttribute>;
  id: Scalars["String"];
  token: StrAttribute;
};

export type RelatedAttributeSchema = RelatedNodeInterface & {
  __typename?: "RelatedAttributeSchema";
  _relation__is_protected?: Maybe<Scalars["Boolean"]>;
  _relation__is_visible?: Maybe<Scalars["Boolean"]>;
  _relation__owner?: Maybe<DataOwner>;
  _relation__source?: Maybe<DataSource>;
  _relation__updated_at?: Maybe<Scalars["DateTime"]>;
  _updated_at?: Maybe<Scalars["DateTime"]>;
  branch: BoolAttribute;
  default_value?: Maybe<AnyAttribute>;
  description?: Maybe<StrAttribute>;
  id: Scalars["String"];
  inherited: BoolAttribute;
  kind: StrAttribute;
  label?: Maybe<StrAttribute>;
  name: StrAttribute;
  optional: BoolAttribute;
  unique: BoolAttribute;
};

export type RelatedAutonomousSystem = RelatedNodeInterface & {
  __typename?: "RelatedAutonomousSystem";
  _relation__is_protected?: Maybe<Scalars["Boolean"]>;
  _relation__is_visible?: Maybe<Scalars["Boolean"]>;
  _relation__owner?: Maybe<DataOwner>;
  _relation__source?: Maybe<DataSource>;
  _relation__updated_at?: Maybe<Scalars["DateTime"]>;
  _updated_at?: Maybe<Scalars["DateTime"]>;
  asn: IntAttribute;
  description?: Maybe<StrAttribute>;
  id: Scalars["String"];
  name: StrAttribute;
  organization?: Maybe<RelatedOrganization>;
};

export type RelatedBgpPeerGroup = RelatedNodeInterface & {
  __typename?: "RelatedBGPPeerGroup";
  _relation__is_protected?: Maybe<Scalars["Boolean"]>;
  _relation__is_visible?: Maybe<Scalars["Boolean"]>;
  _relation__owner?: Maybe<DataOwner>;
  _relation__source?: Maybe<DataSource>;
  _relation__updated_at?: Maybe<Scalars["DateTime"]>;
  _updated_at?: Maybe<Scalars["DateTime"]>;
  description?: Maybe<StrAttribute>;
  export_policies?: Maybe<StrAttribute>;
  id: Scalars["String"];
  import_policies?: Maybe<StrAttribute>;
  local_as?: Maybe<RelatedAutonomousSystem>;
  name: StrAttribute;
  remote_as?: Maybe<RelatedAutonomousSystem>;
};

export type RelatedBgpSession = RelatedNodeInterface & {
  __typename?: "RelatedBGPSession";
  _relation__is_protected?: Maybe<Scalars["Boolean"]>;
  _relation__is_visible?: Maybe<Scalars["Boolean"]>;
  _relation__owner?: Maybe<DataOwner>;
  _relation__source?: Maybe<DataSource>;
  _relation__updated_at?: Maybe<Scalars["DateTime"]>;
  _updated_at?: Maybe<Scalars["DateTime"]>;
  description?: Maybe<StrAttribute>;
  device?: Maybe<RelatedDevice>;
  export_policies?: Maybe<StrAttribute>;
  id: Scalars["String"];
  import_policies?: Maybe<StrAttribute>;
  local_as?: Maybe<RelatedAutonomousSystem>;
  local_ip?: Maybe<RelatedIpAddress>;
  peer_group?: Maybe<RelatedBgpPeerGroup>;
  peer_session?: Maybe<RelatedBgpSession>;
  remote_as?: Maybe<RelatedAutonomousSystem>;
  remote_ip?: Maybe<RelatedIpAddress>;
  role?: Maybe<RelatedRole>;
  status?: Maybe<RelatedStatus>;
  type: StrAttribute;
};

export type RelatedCheck = RelatedNodeInterface & {
  __typename?: "RelatedCheck";
  _relation__is_protected?: Maybe<Scalars["Boolean"]>;
  _relation__is_visible?: Maybe<Scalars["Boolean"]>;
  _relation__owner?: Maybe<DataOwner>;
  _relation__source?: Maybe<DataSource>;
  _relation__updated_at?: Maybe<Scalars["DateTime"]>;
  _updated_at?: Maybe<Scalars["DateTime"]>;
  class_name: StrAttribute;
  description?: Maybe<StrAttribute>;
  file_path: StrAttribute;
  id: Scalars["String"];
  name: StrAttribute;
  query?: Maybe<RelatedGraphQlQuery>;
  rebase: BoolAttribute;
  repository?: Maybe<RelatedRepository>;
  tags: Array<Maybe<RelatedTag>>;
  timeout: IntAttribute;
};

export type RelatedCheckTagsArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
};

export type RelatedCircuit = RelatedNodeInterface & {
  __typename?: "RelatedCircuit";
  _relation__is_protected?: Maybe<Scalars["Boolean"]>;
  _relation__is_visible?: Maybe<Scalars["Boolean"]>;
  _relation__owner?: Maybe<DataOwner>;
  _relation__source?: Maybe<DataSource>;
  _relation__updated_at?: Maybe<Scalars["DateTime"]>;
  _updated_at?: Maybe<Scalars["DateTime"]>;
  circuit_id: StrAttribute;
  description?: Maybe<StrAttribute>;
  endpoints: Array<Maybe<RelatedCircuitEndpoint>>;
  id: Scalars["String"];
  provider?: Maybe<RelatedOrganization>;
  role?: Maybe<RelatedRole>;
  status?: Maybe<RelatedStatus>;
  vendor_id?: Maybe<StrAttribute>;
};

export type RelatedCircuitEndpointsArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
};

export type RelatedCircuitEndpoint = RelatedNodeInterface & {
  __typename?: "RelatedCircuitEndpoint";
  _relation__is_protected?: Maybe<Scalars["Boolean"]>;
  _relation__is_visible?: Maybe<Scalars["Boolean"]>;
  _relation__owner?: Maybe<DataOwner>;
  _relation__source?: Maybe<DataSource>;
  _relation__updated_at?: Maybe<Scalars["DateTime"]>;
  _updated_at?: Maybe<Scalars["DateTime"]>;
  circuit?: Maybe<RelatedCircuit>;
  connected_interface?: Maybe<RelatedInterface>;
  description?: Maybe<StrAttribute>;
  id: Scalars["String"];
  site?: Maybe<RelatedLocation>;
};

export type RelatedDataOwner = {
  description?: Maybe<StrAttribute>;
  /** Unique identifier */
  id?: Maybe<Scalars["String"]>;
  name: StrAttribute;
};

/** Any Entities that stores or produces data. */
export type RelatedDataSource = {
  description?: Maybe<StrAttribute>;
  /** Unique identifier */
  id?: Maybe<Scalars["String"]>;
  name: StrAttribute;
};

export type RelatedDevice = RelatedNodeInterface & {
  __typename?: "RelatedDevice";
  _relation__is_protected?: Maybe<Scalars["Boolean"]>;
  _relation__is_visible?: Maybe<Scalars["Boolean"]>;
  _relation__owner?: Maybe<DataOwner>;
  _relation__source?: Maybe<DataSource>;
  _relation__updated_at?: Maybe<Scalars["DateTime"]>;
  _updated_at?: Maybe<Scalars["DateTime"]>;
  asn?: Maybe<RelatedAutonomousSystem>;
  description?: Maybe<StrAttribute>;
  id: Scalars["String"];
  interfaces: Array<Maybe<RelatedInterface>>;
  name: StrAttribute;
  role?: Maybe<RelatedRole>;
  site?: Maybe<RelatedLocation>;
  status?: Maybe<RelatedStatus>;
  tags: Array<Maybe<RelatedTag>>;
  type: StrAttribute;
};

export type RelatedDeviceInterfacesArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  enabled__value?: InputMaybe<Scalars["Boolean"]>;
  id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  speed__value?: InputMaybe<Scalars["Int"]>;
};

export type RelatedDeviceTagsArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
};

export type RelatedGraphQlQuery = RelatedNodeInterface & {
  __typename?: "RelatedGraphQLQuery";
  _relation__is_protected?: Maybe<Scalars["Boolean"]>;
  _relation__is_visible?: Maybe<Scalars["Boolean"]>;
  _relation__owner?: Maybe<DataOwner>;
  _relation__source?: Maybe<DataSource>;
  _relation__updated_at?: Maybe<Scalars["DateTime"]>;
  _updated_at?: Maybe<Scalars["DateTime"]>;
  description?: Maybe<StrAttribute>;
  id: Scalars["String"];
  name: StrAttribute;
  query: StrAttribute;
  tags: Array<Maybe<RelatedTag>>;
};

export type RelatedGraphQlQueryTagsArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
};

export type RelatedGroup = RelatedDataOwner &
  RelatedNodeInterface & {
    __typename?: "RelatedGroup";
    _relation__is_protected?: Maybe<Scalars["Boolean"]>;
    _relation__is_visible?: Maybe<Scalars["Boolean"]>;
    _relation__owner?: Maybe<DataOwner>;
    _relation__source?: Maybe<DataSource>;
    _relation__updated_at?: Maybe<Scalars["DateTime"]>;
    _updated_at?: Maybe<Scalars["DateTime"]>;
    description?: Maybe<StrAttribute>;
    id: Scalars["String"];
    members: Array<Maybe<RelatedAccount>>;
    name: StrAttribute;
  };

export type RelatedGroupMembersArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  type__value?: InputMaybe<Scalars["String"]>;
};

export type RelatedIpAddress = RelatedNodeInterface & {
  __typename?: "RelatedIPAddress";
  _relation__is_protected?: Maybe<Scalars["Boolean"]>;
  _relation__is_visible?: Maybe<Scalars["Boolean"]>;
  _relation__owner?: Maybe<DataOwner>;
  _relation__source?: Maybe<DataSource>;
  _relation__updated_at?: Maybe<Scalars["DateTime"]>;
  _updated_at?: Maybe<Scalars["DateTime"]>;
  address: StrAttribute;
  description?: Maybe<StrAttribute>;
  id: Scalars["String"];
  interface?: Maybe<RelatedInterface>;
};

export type RelatedInterface = RelatedNodeInterface & {
  __typename?: "RelatedInterface";
  _relation__is_protected?: Maybe<Scalars["Boolean"]>;
  _relation__is_visible?: Maybe<Scalars["Boolean"]>;
  _relation__owner?: Maybe<DataOwner>;
  _relation__source?: Maybe<DataSource>;
  _relation__updated_at?: Maybe<Scalars["DateTime"]>;
  _updated_at?: Maybe<Scalars["DateTime"]>;
  connected_circuit?: Maybe<RelatedCircuitEndpoint>;
  connected_interface?: Maybe<RelatedInterface>;
  description?: Maybe<StrAttribute>;
  device?: Maybe<RelatedDevice>;
  enabled: BoolAttribute;
  id: Scalars["String"];
  ip_addresses: Array<Maybe<RelatedIpAddress>>;
  name: StrAttribute;
  role?: Maybe<RelatedRole>;
  speed: IntAttribute;
  status?: Maybe<RelatedStatus>;
  tags: Array<Maybe<RelatedTag>>;
};

export type RelatedInterfaceIp_AddressesArgs = {
  address__value?: InputMaybe<Scalars["String"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
};

export type RelatedInterfaceTagsArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
};

export type RelatedLocation = RelatedNodeInterface & {
  __typename?: "RelatedLocation";
  _relation__is_protected?: Maybe<Scalars["Boolean"]>;
  _relation__is_visible?: Maybe<Scalars["Boolean"]>;
  _relation__owner?: Maybe<DataOwner>;
  _relation__source?: Maybe<DataSource>;
  _relation__updated_at?: Maybe<Scalars["DateTime"]>;
  _updated_at?: Maybe<Scalars["DateTime"]>;
  description?: Maybe<StrAttribute>;
  id: Scalars["String"];
  name: StrAttribute;
  tags: Array<Maybe<RelatedTag>>;
  type: StrAttribute;
};

export type RelatedLocationTagsArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
};

export type RelatedNodeInput = {
  _relation__is_protected?: InputMaybe<Scalars["Boolean"]>;
  _relation__is_visible?: InputMaybe<Scalars["Boolean"]>;
  _relation__owner?: InputMaybe<Scalars["String"]>;
  _relation__source?: InputMaybe<Scalars["String"]>;
  id: Scalars["String"];
};

export type RelatedNodeInterface = {
  _relation__is_protected?: Maybe<Scalars["Boolean"]>;
  _relation__is_visible?: Maybe<Scalars["Boolean"]>;
  _relation__updated_at?: Maybe<Scalars["DateTime"]>;
};

export type RelatedOrganization = RelatedNodeInterface & {
  __typename?: "RelatedOrganization";
  _relation__is_protected?: Maybe<Scalars["Boolean"]>;
  _relation__is_visible?: Maybe<Scalars["Boolean"]>;
  _relation__owner?: Maybe<DataOwner>;
  _relation__source?: Maybe<DataSource>;
  _relation__updated_at?: Maybe<Scalars["DateTime"]>;
  _updated_at?: Maybe<Scalars["DateTime"]>;
  description?: Maybe<StrAttribute>;
  id: Scalars["String"];
  name: StrAttribute;
  tags: Array<Maybe<RelatedTag>>;
};

export type RelatedOrganizationTagsArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
};

export type RelatedRFile = RelatedNodeInterface & {
  __typename?: "RelatedRFile";
  _relation__is_protected?: Maybe<Scalars["Boolean"]>;
  _relation__is_visible?: Maybe<Scalars["Boolean"]>;
  _relation__owner?: Maybe<DataOwner>;
  _relation__source?: Maybe<DataSource>;
  _relation__updated_at?: Maybe<Scalars["DateTime"]>;
  _updated_at?: Maybe<Scalars["DateTime"]>;
  description?: Maybe<StrAttribute>;
  id: Scalars["String"];
  name: StrAttribute;
  query?: Maybe<RelatedGraphQlQuery>;
  tags: Array<Maybe<RelatedTag>>;
  template_path: StrAttribute;
  template_repository?: Maybe<RelatedRepository>;
};

export type RelatedRFileTagsArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
};

export type RelatedRelationshipSchema = RelatedNodeInterface & {
  __typename?: "RelatedRelationshipSchema";
  _relation__is_protected?: Maybe<Scalars["Boolean"]>;
  _relation__is_visible?: Maybe<Scalars["Boolean"]>;
  _relation__owner?: Maybe<DataOwner>;
  _relation__source?: Maybe<DataSource>;
  _relation__updated_at?: Maybe<Scalars["DateTime"]>;
  _updated_at?: Maybe<Scalars["DateTime"]>;
  branch: BoolAttribute;
  cardinality: StrAttribute;
  description?: Maybe<StrAttribute>;
  id: Scalars["String"];
  identifier: StrAttribute;
  inherited: BoolAttribute;
  label?: Maybe<StrAttribute>;
  name: StrAttribute;
  optional: BoolAttribute;
  peer: StrAttribute;
};

export type RelatedRepository = RelatedDataOwner &
  RelatedDataSource &
  RelatedNodeInterface & {
    __typename?: "RelatedRepository";
    _relation__is_protected?: Maybe<Scalars["Boolean"]>;
    _relation__is_visible?: Maybe<Scalars["Boolean"]>;
    _relation__owner?: Maybe<DataOwner>;
    _relation__source?: Maybe<DataSource>;
    _relation__updated_at?: Maybe<Scalars["DateTime"]>;
    _updated_at?: Maybe<Scalars["DateTime"]>;
    account?: Maybe<RelatedAccount>;
    checks: Array<Maybe<RelatedCheck>>;
    commit?: Maybe<StrAttribute>;
    default_branch: StrAttribute;
    description?: Maybe<StrAttribute>;
    id: Scalars["String"];
    location: StrAttribute;
    name: StrAttribute;
    password?: Maybe<StrAttribute>;
    queries: Array<Maybe<RelatedGraphQlQuery>>;
    rfiles: Array<Maybe<RelatedRFile>>;
    tags: Array<Maybe<RelatedTag>>;
    transform_python: Array<Maybe<RelatedTransformPython>>;
    type: StrAttribute;
    username?: Maybe<StrAttribute>;
  };

export type RelatedRepositoryChecksArgs = {
  class_name__value?: InputMaybe<Scalars["String"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  file_path__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  rebase__value?: InputMaybe<Scalars["Boolean"]>;
  timeout__value?: InputMaybe<Scalars["Int"]>;
};

export type RelatedRepositoryQueriesArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  query__value?: InputMaybe<Scalars["String"]>;
};

export type RelatedRepositoryRfilesArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  template_path__value?: InputMaybe<Scalars["String"]>;
};

export type RelatedRepositoryTagsArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
};

export type RelatedRepositoryTransform_PythonArgs = {
  class_name__value?: InputMaybe<Scalars["String"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  file_path__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  rebase__value?: InputMaybe<Scalars["Boolean"]>;
  timeout__value?: InputMaybe<Scalars["Int"]>;
  url__value?: InputMaybe<Scalars["String"]>;
};

export type RelatedRole = RelatedNodeInterface & {
  __typename?: "RelatedRole";
  _relation__is_protected?: Maybe<Scalars["Boolean"]>;
  _relation__is_visible?: Maybe<Scalars["Boolean"]>;
  _relation__owner?: Maybe<DataOwner>;
  _relation__source?: Maybe<DataSource>;
  _relation__updated_at?: Maybe<Scalars["DateTime"]>;
  _updated_at?: Maybe<Scalars["DateTime"]>;
  description?: Maybe<StrAttribute>;
  id: Scalars["String"];
  name: StrAttribute;
};

export type RelatedStatus = RelatedNodeInterface & {
  __typename?: "RelatedStatus";
  _relation__is_protected?: Maybe<Scalars["Boolean"]>;
  _relation__is_visible?: Maybe<Scalars["Boolean"]>;
  _relation__owner?: Maybe<DataOwner>;
  _relation__source?: Maybe<DataSource>;
  _relation__updated_at?: Maybe<Scalars["DateTime"]>;
  _updated_at?: Maybe<Scalars["DateTime"]>;
  description?: Maybe<StrAttribute>;
  id: Scalars["String"];
  name: StrAttribute;
};

export type RelatedTag = RelatedNodeInterface & {
  __typename?: "RelatedTag";
  _relation__is_protected?: Maybe<Scalars["Boolean"]>;
  _relation__is_visible?: Maybe<Scalars["Boolean"]>;
  _relation__owner?: Maybe<DataOwner>;
  _relation__source?: Maybe<DataSource>;
  _relation__updated_at?: Maybe<Scalars["DateTime"]>;
  _updated_at?: Maybe<Scalars["DateTime"]>;
  description?: Maybe<StrAttribute>;
  id: Scalars["String"];
  name: StrAttribute;
};

export type RelatedTransformPython = RelatedNodeInterface & {
  __typename?: "RelatedTransformPython";
  _relation__is_protected?: Maybe<Scalars["Boolean"]>;
  _relation__is_visible?: Maybe<Scalars["Boolean"]>;
  _relation__owner?: Maybe<DataOwner>;
  _relation__source?: Maybe<DataSource>;
  _relation__updated_at?: Maybe<Scalars["DateTime"]>;
  _updated_at?: Maybe<Scalars["DateTime"]>;
  class_name: StrAttribute;
  description?: Maybe<StrAttribute>;
  file_path: StrAttribute;
  id: Scalars["String"];
  name: StrAttribute;
  query?: Maybe<RelatedGraphQlQuery>;
  rebase: BoolAttribute;
  repository?: Maybe<RelatedRepository>;
  tags: Array<Maybe<RelatedTag>>;
  timeout: IntAttribute;
  url: StrAttribute;
};

export type RelatedTransformPythonTagsArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
};

export type RelationshipSchema = {
  __typename?: "RelationshipSchema";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  branch: BoolAttribute;
  cardinality: StrAttribute;
  description?: Maybe<StrAttribute>;
  id: Scalars["String"];
  identifier: StrAttribute;
  inherited: BoolAttribute;
  label?: Maybe<StrAttribute>;
  name: StrAttribute;
  optional: BoolAttribute;
  peer: StrAttribute;
};

export type RelationshipSchemaCreate = {
  __typename?: "RelationshipSchemaCreate";
  object?: Maybe<RelationshipSchema>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type RelationshipSchemaCreateInput = {
  branch: BoolAttributeInput;
  cardinality: StringAttributeInput;
  description?: InputMaybe<StringAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  identifier: StringAttributeInput;
  inherited: BoolAttributeInput;
  label?: InputMaybe<StringAttributeInput>;
  name: StringAttributeInput;
  optional: BoolAttributeInput;
  peer: StringAttributeInput;
};

export type RelationshipSchemaDelete = {
  __typename?: "RelationshipSchemaDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

export type RelationshipSchemaUpdate = {
  __typename?: "RelationshipSchemaUpdate";
  object?: Maybe<RelationshipSchema>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type RelationshipSchemaUpdateInput = {
  branch?: InputMaybe<BoolAttributeInput>;
  cardinality?: InputMaybe<StringAttributeInput>;
  description?: InputMaybe<StringAttributeInput>;
  id: Scalars["String"];
  identifier?: InputMaybe<StringAttributeInput>;
  inherited?: InputMaybe<BoolAttributeInput>;
  label?: InputMaybe<StringAttributeInput>;
  name?: InputMaybe<StringAttributeInput>;
  optional?: InputMaybe<BoolAttributeInput>;
  peer?: InputMaybe<StringAttributeInput>;
};

export type Repository = DataOwner &
  DataSource & {
    __typename?: "Repository";
    _updated_at?: Maybe<Scalars["DateTime"]>;
    account?: Maybe<RelatedAccount>;
    checks: Array<Maybe<RelatedCheck>>;
    commit?: Maybe<StrAttribute>;
    default_branch: StrAttribute;
    description?: Maybe<StrAttribute>;
    id: Scalars["String"];
    location: StrAttribute;
    name: StrAttribute;
    password?: Maybe<StrAttribute>;
    queries: Array<Maybe<RelatedGraphQlQuery>>;
    rfiles: Array<Maybe<RelatedRFile>>;
    tags: Array<Maybe<RelatedTag>>;
    transform_python: Array<Maybe<RelatedTransformPython>>;
    type: StrAttribute;
    username?: Maybe<StrAttribute>;
  };

export type RepositoryChecksArgs = {
  class_name__value?: InputMaybe<Scalars["String"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  file_path__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  rebase__value?: InputMaybe<Scalars["Boolean"]>;
  timeout__value?: InputMaybe<Scalars["Int"]>;
};

export type RepositoryQueriesArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  query__value?: InputMaybe<Scalars["String"]>;
};

export type RepositoryRfilesArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  template_path__value?: InputMaybe<Scalars["String"]>;
};

export type RepositoryTagsArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
};

export type RepositoryTransform_PythonArgs = {
  class_name__value?: InputMaybe<Scalars["String"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  file_path__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  rebase__value?: InputMaybe<Scalars["Boolean"]>;
  timeout__value?: InputMaybe<Scalars["Int"]>;
  url__value?: InputMaybe<Scalars["String"]>;
};

export type RepositoryCreate = {
  __typename?: "RepositoryCreate";
  object?: Maybe<Repository>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type RepositoryCreateInput = {
  account?: InputMaybe<RelatedNodeInput>;
  checks?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  commit?: InputMaybe<StringAttributeInput>;
  default_branch?: InputMaybe<StringAttributeInput>;
  description?: InputMaybe<StringAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  location: StringAttributeInput;
  name: StringAttributeInput;
  password?: InputMaybe<StringAttributeInput>;
  queries?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  rfiles?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  transform_python?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  type?: InputMaybe<StringAttributeInput>;
  username?: InputMaybe<StringAttributeInput>;
};

export type RepositoryDelete = {
  __typename?: "RepositoryDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

export type RepositoryUpdate = {
  __typename?: "RepositoryUpdate";
  object?: Maybe<Repository>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type RepositoryUpdateInput = {
  account?: InputMaybe<RelatedNodeInput>;
  checks?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  commit?: InputMaybe<StringAttributeInput>;
  default_branch?: InputMaybe<StringAttributeInput>;
  description?: InputMaybe<StringAttributeInput>;
  id: Scalars["String"];
  location?: InputMaybe<StringAttributeInput>;
  name?: InputMaybe<StringAttributeInput>;
  password?: InputMaybe<StringAttributeInput>;
  queries?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  rfiles?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  transform_python?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  type?: InputMaybe<StringAttributeInput>;
  username?: InputMaybe<StringAttributeInput>;
};

export type Role = {
  __typename?: "Role";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  description?: Maybe<StrAttribute>;
  id: Scalars["String"];
  name: StrAttribute;
};

export type RoleCreate = {
  __typename?: "RoleCreate";
  object?: Maybe<Role>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type RoleCreateInput = {
  description?: InputMaybe<StringAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  name: StringAttributeInput;
};

export type RoleDelete = {
  __typename?: "RoleDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

export type RoleUpdate = {
  __typename?: "RoleUpdate";
  object?: Maybe<Role>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type RoleUpdateInput = {
  description?: InputMaybe<StringAttributeInput>;
  id: Scalars["String"];
  name?: InputMaybe<StringAttributeInput>;
};

export type Status = {
  __typename?: "Status";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  description?: Maybe<StrAttribute>;
  id: Scalars["String"];
  name: StrAttribute;
};

export type StatusCreate = {
  __typename?: "StatusCreate";
  object?: Maybe<Status>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type StatusCreateInput = {
  description?: InputMaybe<StringAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  name: StringAttributeInput;
};

export type StatusDelete = {
  __typename?: "StatusDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

export type StatusUpdate = {
  __typename?: "StatusUpdate";
  object?: Maybe<Status>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type StatusUpdateInput = {
  description?: InputMaybe<StringAttributeInput>;
  id: Scalars["String"];
  name?: InputMaybe<StringAttributeInput>;
};

/** Attribute of type String */
export type StrAttribute = AttributeInterface & {
  __typename?: "StrAttribute";
  id?: Maybe<Scalars["String"]>;
  is_inherited?: Maybe<Scalars["Boolean"]>;
  is_protected?: Maybe<Scalars["Boolean"]>;
  is_visible?: Maybe<Scalars["Boolean"]>;
  owner?: Maybe<DataOwner>;
  source?: Maybe<DataSource>;
  updated_at?: Maybe<Scalars["DateTime"]>;
  value?: Maybe<Scalars["String"]>;
};

export type StringAttributeInput = {
  is_protected?: InputMaybe<Scalars["Boolean"]>;
  is_visible?: InputMaybe<Scalars["Boolean"]>;
  owner?: InputMaybe<Scalars["String"]>;
  source?: InputMaybe<Scalars["String"]>;
  value?: InputMaybe<Scalars["String"]>;
};

export type Subscription = {
  __typename?: "Subscription";
  event?: Maybe<Scalars["GenericScalar"]>;
  query?: Maybe<Scalars["GenericScalar"]>;
};

export type SubscriptionEventArgs = {
  topics?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type SubscriptionQueryArgs = {
  name?: InputMaybe<Scalars["String"]>;
  params?: InputMaybe<Scalars["GenericScalar"]>;
};

export type Tag = {
  __typename?: "Tag";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  description?: Maybe<StrAttribute>;
  id: Scalars["String"];
  name: StrAttribute;
};

export type TagCreate = {
  __typename?: "TagCreate";
  object?: Maybe<Tag>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type TagCreateInput = {
  description?: InputMaybe<StringAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  name: StringAttributeInput;
};

export type TagDelete = {
  __typename?: "TagDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

export type TagUpdate = {
  __typename?: "TagUpdate";
  object?: Maybe<Tag>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type TagUpdateInput = {
  description?: InputMaybe<StringAttributeInput>;
  id: Scalars["String"];
  name?: InputMaybe<StringAttributeInput>;
};

export type TransformPython = {
  __typename?: "TransformPython";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  class_name: StrAttribute;
  description?: Maybe<StrAttribute>;
  file_path: StrAttribute;
  id: Scalars["String"];
  name: StrAttribute;
  query?: Maybe<RelatedGraphQlQuery>;
  rebase: BoolAttribute;
  repository?: Maybe<RelatedRepository>;
  tags: Array<Maybe<RelatedTag>>;
  timeout: IntAttribute;
  url: StrAttribute;
};

export type TransformPythonTagsArgs = {
  description__value?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
};

export type TransformPythonCreate = {
  __typename?: "TransformPythonCreate";
  object?: Maybe<TransformPython>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type TransformPythonCreateInput = {
  class_name: StringAttributeInput;
  description?: InputMaybe<StringAttributeInput>;
  file_path: StringAttributeInput;
  id?: InputMaybe<Scalars["String"]>;
  name: StringAttributeInput;
  query?: InputMaybe<RelatedNodeInput>;
  rebase: BoolAttributeInput;
  repository: RelatedNodeInput;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  timeout?: InputMaybe<IntAttributeInput>;
  url: StringAttributeInput;
};

export type TransformPythonDelete = {
  __typename?: "TransformPythonDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

export type TransformPythonUpdate = {
  __typename?: "TransformPythonUpdate";
  object?: Maybe<TransformPython>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type TransformPythonUpdateInput = {
  class_name?: InputMaybe<StringAttributeInput>;
  description?: InputMaybe<StringAttributeInput>;
  file_path?: InputMaybe<StringAttributeInput>;
  id: Scalars["String"];
  name?: InputMaybe<StringAttributeInput>;
  query?: InputMaybe<RelatedNodeInput>;
  rebase?: InputMaybe<BoolAttributeInput>;
  repository?: InputMaybe<RelatedNodeInput>;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  timeout?: InputMaybe<IntAttributeInput>;
  url?: InputMaybe<StringAttributeInput>;
};
