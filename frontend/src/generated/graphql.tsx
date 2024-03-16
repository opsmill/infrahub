export type Maybe<T> = T | null;
export type InputMaybe<T> = Maybe<T>;
export type Exact<T extends { [key: string]: unknown }> = { [K in keyof T]: T[K] };
export type MakeOptional<T, K extends keyof T> = Omit<T, K> & { [SubKey in K]?: Maybe<T[SubKey]> };
export type MakeMaybe<T, K extends keyof T> = Omit<T, K> & { [SubKey in K]: Maybe<T[SubKey]> };
/** All built-in and custom scalars, mapped to their actual values */
export type Scalars = {
  ID: string;
  String: string;
  Boolean: boolean;
  Int: number;
  Float: number;
  DateTime: any;
  GenericScalar: any;
  UUID: any;
};

/** Attribute of type GenericScalar */
export type AnyAttribute = AttributeInterface & {
  __typename?: "AnyAttribute";
  id?: Maybe<Scalars["String"]>;
  is_inherited?: Maybe<Scalars["Boolean"]>;
  is_protected?: Maybe<Scalars["Boolean"]>;
  is_visible?: Maybe<Scalars["Boolean"]>;
  owner?: Maybe<LineageOwner>;
  source?: Maybe<LineageSource>;
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

/** Branch */
export type Branch = {
  __typename?: "Branch";
  branched_from?: Maybe<Scalars["String"]>;
  created_at?: Maybe<Scalars["String"]>;
  description?: Maybe<Scalars["String"]>;
  has_schema_changes?: Maybe<Scalars["Boolean"]>;
  id: Scalars["String"];
  is_default?: Maybe<Scalars["Boolean"]>;
  is_isolated?: Maybe<Scalars["Boolean"]>;
  name: Scalars["String"];
  origin_branch?: Maybe<Scalars["String"]>;
  sync_with_git?: Maybe<Scalars["Boolean"]>;
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
  is_isolated?: InputMaybe<Scalars["Boolean"]>;
  name: Scalars["String"];
  origin_branch?: InputMaybe<Scalars["String"]>;
  sync_with_git?: InputMaybe<Scalars["Boolean"]>;
};

export type BranchDelete = {
  __typename?: "BranchDelete";
  ok?: Maybe<Scalars["Boolean"]>;
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

export type BranchUpdate = {
  __typename?: "BranchUpdate";
  ok?: Maybe<Scalars["Boolean"]>;
};

export type BranchUpdateInput = {
  description?: InputMaybe<Scalars["String"]>;
  is_isolated?: InputMaybe<Scalars["Boolean"]>;
  name: Scalars["String"];
};

export type BranchValidate = {
  __typename?: "BranchValidate";
  messages?: Maybe<Array<Maybe<Scalars["String"]>>>;
  object?: Maybe<Branch>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** Represents the role of an object */
export type BuiltinRole = CoreNode & {
  __typename?: "BuiltinRole";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  description?: Maybe<TextAttribute>;
  display_label?: Maybe<Scalars["String"]>;
  id: Scalars["String"];
  label?: Maybe<TextAttribute>;
  member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  name: TextAttribute;
  subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
};

/** Represents the role of an object */
export type BuiltinRoleMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Represents the role of an object */
export type BuiltinRoleSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Represents the role of an object */
export type BuiltinRoleCreate = {
  __typename?: "BuiltinRoleCreate";
  object?: Maybe<BuiltinRole>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type BuiltinRoleCreateInput = {
  description?: InputMaybe<TextAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  label?: InputMaybe<TextAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name: TextAttributeInput;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** Represents the role of an object */
export type BuiltinRoleDelete = {
  __typename?: "BuiltinRoleDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** Represents the role of an object */
export type BuiltinRoleUpdate = {
  __typename?: "BuiltinRoleUpdate";
  object?: Maybe<BuiltinRole>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type BuiltinRoleUpdateInput = {
  description?: InputMaybe<TextAttributeInput>;
  id: Scalars["String"];
  label?: InputMaybe<TextAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** Represents the role of an object */
export type BuiltinRoleUpsert = {
  __typename?: "BuiltinRoleUpsert";
  object?: Maybe<BuiltinRole>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** Status represents the current state of an object: active, maintenance */
export type BuiltinStatus = CoreNode & {
  __typename?: "BuiltinStatus";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  description?: Maybe<TextAttribute>;
  display_label?: Maybe<Scalars["String"]>;
  id: Scalars["String"];
  label?: Maybe<TextAttribute>;
  member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  name: TextAttribute;
  subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
};

/** Status represents the current state of an object: active, maintenance */
export type BuiltinStatusMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Status represents the current state of an object: active, maintenance */
export type BuiltinStatusSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Status represents the current state of an object: active, maintenance */
export type BuiltinStatusCreate = {
  __typename?: "BuiltinStatusCreate";
  object?: Maybe<BuiltinStatus>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type BuiltinStatusCreateInput = {
  description?: InputMaybe<TextAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  label?: InputMaybe<TextAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name: TextAttributeInput;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** Status represents the current state of an object: active, maintenance */
export type BuiltinStatusDelete = {
  __typename?: "BuiltinStatusDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** Status represents the current state of an object: active, maintenance */
export type BuiltinStatusUpdate = {
  __typename?: "BuiltinStatusUpdate";
  object?: Maybe<BuiltinStatus>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type BuiltinStatusUpdateInput = {
  description?: InputMaybe<TextAttributeInput>;
  id: Scalars["String"];
  label?: InputMaybe<TextAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** Status represents the current state of an object: active, maintenance */
export type BuiltinStatusUpsert = {
  __typename?: "BuiltinStatusUpsert";
  object?: Maybe<BuiltinStatus>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** Standard Tag object to attached to other objects to provide some context. */
export type BuiltinTag = CoreNode & {
  __typename?: "BuiltinTag";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  description?: Maybe<TextAttribute>;
  display_label?: Maybe<Scalars["String"]>;
  id: Scalars["String"];
  member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  name: TextAttribute;
  subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
};

/** Standard Tag object to attached to other objects to provide some context. */
export type BuiltinTagMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Standard Tag object to attached to other objects to provide some context. */
export type BuiltinTagSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Standard Tag object to attached to other objects to provide some context. */
export type BuiltinTagCreate = {
  __typename?: "BuiltinTagCreate";
  object?: Maybe<BuiltinTag>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type BuiltinTagCreateInput = {
  description?: InputMaybe<TextAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name: TextAttributeInput;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** Standard Tag object to attached to other objects to provide some context. */
export type BuiltinTagDelete = {
  __typename?: "BuiltinTagDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** Standard Tag object to attached to other objects to provide some context. */
export type BuiltinTagUpdate = {
  __typename?: "BuiltinTagUpdate";
  object?: Maybe<BuiltinTag>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type BuiltinTagUpdateInput = {
  description?: InputMaybe<TextAttributeInput>;
  id: Scalars["String"];
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** Standard Tag object to attached to other objects to provide some context. */
export type BuiltinTagUpsert = {
  __typename?: "BuiltinTagUpsert";
  object?: Maybe<BuiltinTag>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** An enumeration. */
export enum CheckType {
  All = "ALL",
  Artifact = "ARTIFACT",
  Data = "DATA",
  Repository = "REPOSITORY",
  Schema = "SCHEMA",
  Test = "TEST",
  User = "USER",
}

/** Attribute of type Checkbox */
export type CheckboxAttribute = AttributeInterface & {
  __typename?: "CheckboxAttribute";
  id?: Maybe<Scalars["String"]>;
  is_inherited?: Maybe<Scalars["Boolean"]>;
  is_protected?: Maybe<Scalars["Boolean"]>;
  is_visible?: Maybe<Scalars["Boolean"]>;
  owner?: Maybe<LineageOwner>;
  source?: Maybe<LineageSource>;
  updated_at?: Maybe<Scalars["DateTime"]>;
  value?: Maybe<Scalars["Boolean"]>;
};

export type CheckboxAttributeInput = {
  is_protected?: InputMaybe<Scalars["Boolean"]>;
  is_visible?: InputMaybe<Scalars["Boolean"]>;
  owner?: InputMaybe<Scalars["String"]>;
  source?: InputMaybe<Scalars["String"]>;
  value?: InputMaybe<Scalars["Boolean"]>;
};

/** User Account for Infrahub */
export type CoreAccount = CoreNode &
  LineageOwner &
  LineageSource & {
    __typename?: "CoreAccount";
    _updated_at?: Maybe<Scalars["DateTime"]>;
    description?: Maybe<TextAttribute>;
    display_label?: Maybe<Scalars["String"]>;
    id: Scalars["String"];
    label?: Maybe<TextAttribute>;
    member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    name: TextAttribute;
    password: TextAttribute;
    role?: Maybe<TextAttribute>;
    subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    type?: Maybe<TextAttribute>;
  };

/** User Account for Infrahub */
export type CoreAccountMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** User Account for Infrahub */
export type CoreAccountSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** User Account for Infrahub */
export type CoreAccountCreate = {
  __typename?: "CoreAccountCreate";
  object?: Maybe<CoreAccount>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreAccountCreateInput = {
  description?: InputMaybe<TextAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  label?: InputMaybe<TextAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name: TextAttributeInput;
  password: TextAttributeInput;
  role?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  type?: InputMaybe<TextAttributeInput>;
};

/** User Account for Infrahub */
export type CoreAccountDelete = {
  __typename?: "CoreAccountDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreAccountSelfUpdate = {
  __typename?: "CoreAccountSelfUpdate";
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreAccountTokenCreate = {
  __typename?: "CoreAccountTokenCreate";
  object?: Maybe<CoreAccountTokenType>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreAccountTokenCreateInput = {
  /** Timestamp when the token expires */
  expiration?: InputMaybe<Scalars["String"]>;
  /** The name of the token */
  name?: InputMaybe<Scalars["String"]>;
};

export type CoreAccountTokenType = {
  __typename?: "CoreAccountTokenType";
  token?: Maybe<ValueType>;
};

/** User Account for Infrahub */
export type CoreAccountUpdate = {
  __typename?: "CoreAccountUpdate";
  object?: Maybe<CoreAccount>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreAccountUpdateInput = {
  description?: InputMaybe<TextAttributeInput>;
  id: Scalars["String"];
  label?: InputMaybe<TextAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name?: InputMaybe<TextAttributeInput>;
  password?: InputMaybe<TextAttributeInput>;
  role?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  type?: InputMaybe<TextAttributeInput>;
};

export type CoreAccountUpdateSelfInput = {
  /** The new description */
  description?: InputMaybe<Scalars["String"]>;
  /** The new password */
  password?: InputMaybe<Scalars["String"]>;
};

/** User Account for Infrahub */
export type CoreAccountUpsert = {
  __typename?: "CoreAccountUpsert";
  object?: Maybe<CoreAccount>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreArtifact = CoreNode &
  CoreTaskTarget & {
    __typename?: "CoreArtifact";
    _updated_at?: Maybe<Scalars["DateTime"]>;
    checksum?: Maybe<TextAttribute>;
    content_type: TextAttribute;
    definition?: Maybe<NestedEdgedCoreArtifactDefinition>;
    display_label?: Maybe<Scalars["String"]>;
    id: Scalars["String"];
    member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    name: TextAttribute;
    object?: Maybe<NestedEdgedCoreNode>;
    parameters?: Maybe<JsonAttribute>;
    status: TextAttribute;
    /** ID of the file in the object store */
    storage_id?: Maybe<TextAttribute>;
    subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  };

export type CoreArtifactMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

export type CoreArtifactSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A check related to an artifact */
export type CoreArtifactCheck = CoreCheck &
  CoreNode & {
    __typename?: "CoreArtifactCheck";
    _updated_at?: Maybe<Scalars["DateTime"]>;
    artifact_id?: Maybe<TextAttribute>;
    changed?: Maybe<CheckboxAttribute>;
    checksum?: Maybe<TextAttribute>;
    conclusion?: Maybe<TextAttribute>;
    created_at?: Maybe<TextAttribute>;
    display_label?: Maybe<Scalars["String"]>;
    id: Scalars["String"];
    kind: TextAttribute;
    label?: Maybe<TextAttribute>;
    line_number?: Maybe<NumberAttribute>;
    member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    message?: Maybe<TextAttribute>;
    name?: Maybe<TextAttribute>;
    origin: TextAttribute;
    severity?: Maybe<TextAttribute>;
    storage_id?: Maybe<TextAttribute>;
    subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    validator?: Maybe<NestedEdgedCoreValidator>;
  };

/** A check related to an artifact */
export type CoreArtifactCheckMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A check related to an artifact */
export type CoreArtifactCheckSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A check related to an artifact */
export type CoreArtifactCheckCreate = {
  __typename?: "CoreArtifactCheckCreate";
  object?: Maybe<CoreArtifactCheck>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreArtifactCheckCreateInput = {
  artifact_id?: InputMaybe<TextAttributeInput>;
  changed?: InputMaybe<CheckboxAttributeInput>;
  checksum?: InputMaybe<TextAttributeInput>;
  conclusion?: InputMaybe<TextAttributeInput>;
  created_at?: InputMaybe<TextAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  kind: TextAttributeInput;
  label?: InputMaybe<TextAttributeInput>;
  line_number?: InputMaybe<NumberAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  message?: InputMaybe<TextAttributeInput>;
  name?: InputMaybe<TextAttributeInput>;
  origin: TextAttributeInput;
  severity?: InputMaybe<TextAttributeInput>;
  storage_id?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  validator: RelatedNodeInput;
};

/** A check related to an artifact */
export type CoreArtifactCheckDelete = {
  __typename?: "CoreArtifactCheckDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A check related to an artifact */
export type CoreArtifactCheckUpdate = {
  __typename?: "CoreArtifactCheckUpdate";
  object?: Maybe<CoreArtifactCheck>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreArtifactCheckUpdateInput = {
  artifact_id?: InputMaybe<TextAttributeInput>;
  changed?: InputMaybe<CheckboxAttributeInput>;
  checksum?: InputMaybe<TextAttributeInput>;
  conclusion?: InputMaybe<TextAttributeInput>;
  created_at?: InputMaybe<TextAttributeInput>;
  id: Scalars["String"];
  kind?: InputMaybe<TextAttributeInput>;
  label?: InputMaybe<TextAttributeInput>;
  line_number?: InputMaybe<NumberAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  message?: InputMaybe<TextAttributeInput>;
  name?: InputMaybe<TextAttributeInput>;
  origin?: InputMaybe<TextAttributeInput>;
  severity?: InputMaybe<TextAttributeInput>;
  storage_id?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  validator?: InputMaybe<RelatedNodeInput>;
};

/** A check related to an artifact */
export type CoreArtifactCheckUpsert = {
  __typename?: "CoreArtifactCheckUpsert";
  object?: Maybe<CoreArtifactCheck>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreArtifactCreate = {
  __typename?: "CoreArtifactCreate";
  object?: Maybe<CoreArtifact>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreArtifactCreateInput = {
  checksum?: InputMaybe<TextAttributeInput>;
  content_type: TextAttributeInput;
  definition: RelatedNodeInput;
  id?: InputMaybe<Scalars["String"]>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name: TextAttributeInput;
  object: RelatedNodeInput;
  parameters?: InputMaybe<JsonAttributeInput>;
  status: TextAttributeInput;
  /** ID of the file in the object store */
  storage_id?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

export type CoreArtifactDefinition = CoreNode &
  CoreTaskTarget & {
    __typename?: "CoreArtifactDefinition";
    _updated_at?: Maybe<Scalars["DateTime"]>;
    artifact_name: TextAttribute;
    content_type: TextAttribute;
    description?: Maybe<TextAttribute>;
    display_label?: Maybe<Scalars["String"]>;
    id: Scalars["String"];
    member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    name: TextAttribute;
    parameters: JsonAttribute;
    subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    targets?: Maybe<NestedEdgedCoreGroup>;
    transformation?: Maybe<NestedEdgedCoreTransformation>;
  };

export type CoreArtifactDefinitionMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

export type CoreArtifactDefinitionSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

export type CoreArtifactDefinitionCreate = {
  __typename?: "CoreArtifactDefinitionCreate";
  object?: Maybe<CoreArtifactDefinition>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreArtifactDefinitionCreateInput = {
  artifact_name: TextAttributeInput;
  content_type: TextAttributeInput;
  description?: InputMaybe<TextAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name: TextAttributeInput;
  parameters: JsonAttributeInput;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  targets: RelatedNodeInput;
  transformation: RelatedNodeInput;
};

export type CoreArtifactDefinitionDelete = {
  __typename?: "CoreArtifactDefinitionDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreArtifactDefinitionUpdate = {
  __typename?: "CoreArtifactDefinitionUpdate";
  object?: Maybe<CoreArtifactDefinition>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreArtifactDefinitionUpdateInput = {
  artifact_name?: InputMaybe<TextAttributeInput>;
  content_type?: InputMaybe<TextAttributeInput>;
  description?: InputMaybe<TextAttributeInput>;
  id: Scalars["String"];
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name?: InputMaybe<TextAttributeInput>;
  parameters?: InputMaybe<JsonAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  targets?: InputMaybe<RelatedNodeInput>;
  transformation?: InputMaybe<RelatedNodeInput>;
};

export type CoreArtifactDefinitionUpsert = {
  __typename?: "CoreArtifactDefinitionUpsert";
  object?: Maybe<CoreArtifactDefinition>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreArtifactDelete = {
  __typename?: "CoreArtifactDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** Extend a node to be associated with artifacts */
export type CoreArtifactTarget = {
  artifacts?: Maybe<NestedPaginatedCoreArtifact>;
  display_label?: Maybe<Scalars["String"]>;
  /** Unique identifier */
  id?: Maybe<Scalars["String"]>;
  member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
};

/** Extend a node to be associated with artifacts */
export type CoreArtifactTargetArtifactsArgs = {
  checksum__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checksum__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checksum__owner__id?: InputMaybe<Scalars["ID"]>;
  checksum__source__id?: InputMaybe<Scalars["ID"]>;
  checksum__value?: InputMaybe<Scalars["String"]>;
  checksum__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  content_type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  content_type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  content_type__owner__id?: InputMaybe<Scalars["ID"]>;
  content_type__source__id?: InputMaybe<Scalars["ID"]>;
  content_type__value?: InputMaybe<Scalars["String"]>;
  content_type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  parameters__is_protected?: InputMaybe<Scalars["Boolean"]>;
  parameters__is_visible?: InputMaybe<Scalars["Boolean"]>;
  parameters__owner__id?: InputMaybe<Scalars["ID"]>;
  parameters__source__id?: InputMaybe<Scalars["ID"]>;
  parameters__value?: InputMaybe<Scalars["GenericScalar"]>;
  parameters__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  status__is_protected?: InputMaybe<Scalars["Boolean"]>;
  status__is_visible?: InputMaybe<Scalars["Boolean"]>;
  status__owner__id?: InputMaybe<Scalars["ID"]>;
  status__source__id?: InputMaybe<Scalars["ID"]>;
  status__value?: InputMaybe<Scalars["String"]>;
  status__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  storage_id__is_protected?: InputMaybe<Scalars["Boolean"]>;
  storage_id__is_visible?: InputMaybe<Scalars["Boolean"]>;
  storage_id__owner__id?: InputMaybe<Scalars["ID"]>;
  storage_id__source__id?: InputMaybe<Scalars["ID"]>;
  storage_id__value?: InputMaybe<Scalars["String"]>;
  storage_id__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

/** Extend a node to be associated with artifacts */
export type CoreArtifactTargetMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Extend a node to be associated with artifacts */
export type CoreArtifactTargetSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A thread related to an artifact on a proposed change */
export type CoreArtifactThread = CoreNode &
  CoreThread & {
    __typename?: "CoreArtifactThread";
    _updated_at?: Maybe<Scalars["DateTime"]>;
    artifact_id?: Maybe<TextAttribute>;
    change?: Maybe<NestedEdgedCoreProposedChange>;
    comments?: Maybe<NestedPaginatedCoreThreadComment>;
    created_at?: Maybe<TextAttribute>;
    created_by?: Maybe<NestedEdgedCoreAccount>;
    display_label?: Maybe<Scalars["String"]>;
    id: Scalars["String"];
    label?: Maybe<TextAttribute>;
    line_number?: Maybe<NumberAttribute>;
    member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    resolved?: Maybe<CheckboxAttribute>;
    storage_id?: Maybe<TextAttribute>;
    subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  };

/** A thread related to an artifact on a proposed change */
export type CoreArtifactThreadCommentsArgs = {
  created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  created_at__source__id?: InputMaybe<Scalars["ID"]>;
  created_at__value?: InputMaybe<Scalars["String"]>;
  created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  offset?: InputMaybe<Scalars["Int"]>;
  text__is_protected?: InputMaybe<Scalars["Boolean"]>;
  text__is_visible?: InputMaybe<Scalars["Boolean"]>;
  text__owner__id?: InputMaybe<Scalars["ID"]>;
  text__source__id?: InputMaybe<Scalars["ID"]>;
  text__value?: InputMaybe<Scalars["String"]>;
  text__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

/** A thread related to an artifact on a proposed change */
export type CoreArtifactThreadMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A thread related to an artifact on a proposed change */
export type CoreArtifactThreadSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A thread related to an artifact on a proposed change */
export type CoreArtifactThreadCreate = {
  __typename?: "CoreArtifactThreadCreate";
  object?: Maybe<CoreArtifactThread>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreArtifactThreadCreateInput = {
  artifact_id?: InputMaybe<TextAttributeInput>;
  change: RelatedNodeInput;
  comments?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  created_at?: InputMaybe<TextAttributeInput>;
  created_by?: InputMaybe<RelatedNodeInput>;
  id?: InputMaybe<Scalars["String"]>;
  label?: InputMaybe<TextAttributeInput>;
  line_number?: InputMaybe<NumberAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  resolved?: InputMaybe<CheckboxAttributeInput>;
  storage_id?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** A thread related to an artifact on a proposed change */
export type CoreArtifactThreadDelete = {
  __typename?: "CoreArtifactThreadDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A thread related to an artifact on a proposed change */
export type CoreArtifactThreadUpdate = {
  __typename?: "CoreArtifactThreadUpdate";
  object?: Maybe<CoreArtifactThread>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreArtifactThreadUpdateInput = {
  artifact_id?: InputMaybe<TextAttributeInput>;
  change?: InputMaybe<RelatedNodeInput>;
  comments?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  created_at?: InputMaybe<TextAttributeInput>;
  created_by?: InputMaybe<RelatedNodeInput>;
  id: Scalars["String"];
  label?: InputMaybe<TextAttributeInput>;
  line_number?: InputMaybe<NumberAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  resolved?: InputMaybe<CheckboxAttributeInput>;
  storage_id?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** A thread related to an artifact on a proposed change */
export type CoreArtifactThreadUpsert = {
  __typename?: "CoreArtifactThreadUpsert";
  object?: Maybe<CoreArtifactThread>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreArtifactUpdate = {
  __typename?: "CoreArtifactUpdate";
  object?: Maybe<CoreArtifact>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreArtifactUpdateInput = {
  checksum?: InputMaybe<TextAttributeInput>;
  content_type?: InputMaybe<TextAttributeInput>;
  definition?: InputMaybe<RelatedNodeInput>;
  id: Scalars["String"];
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name?: InputMaybe<TextAttributeInput>;
  object?: InputMaybe<RelatedNodeInput>;
  parameters?: InputMaybe<JsonAttributeInput>;
  status?: InputMaybe<TextAttributeInput>;
  /** ID of the file in the object store */
  storage_id?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

export type CoreArtifactUpsert = {
  __typename?: "CoreArtifactUpsert";
  object?: Maybe<CoreArtifact>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A validator related to the artifacts */
export type CoreArtifactValidator = CoreNode &
  CoreValidator & {
    __typename?: "CoreArtifactValidator";
    _updated_at?: Maybe<Scalars["DateTime"]>;
    checks?: Maybe<NestedPaginatedCoreCheck>;
    completed_at?: Maybe<TextAttribute>;
    conclusion?: Maybe<TextAttribute>;
    definition?: Maybe<NestedEdgedCoreArtifactDefinition>;
    display_label?: Maybe<Scalars["String"]>;
    id: Scalars["String"];
    label?: Maybe<TextAttribute>;
    member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    proposed_change?: Maybe<NestedEdgedCoreProposedChange>;
    started_at?: Maybe<TextAttribute>;
    state?: Maybe<TextAttribute>;
    subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  };

/** A validator related to the artifacts */
export type CoreArtifactValidatorChecksArgs = {
  conclusion__is_protected?: InputMaybe<Scalars["Boolean"]>;
  conclusion__is_visible?: InputMaybe<Scalars["Boolean"]>;
  conclusion__owner__id?: InputMaybe<Scalars["ID"]>;
  conclusion__source__id?: InputMaybe<Scalars["ID"]>;
  conclusion__value?: InputMaybe<Scalars["String"]>;
  conclusion__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  created_at__source__id?: InputMaybe<Scalars["ID"]>;
  created_at__value?: InputMaybe<Scalars["String"]>;
  created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  kind__is_protected?: InputMaybe<Scalars["Boolean"]>;
  kind__is_visible?: InputMaybe<Scalars["Boolean"]>;
  kind__owner__id?: InputMaybe<Scalars["ID"]>;
  kind__source__id?: InputMaybe<Scalars["ID"]>;
  kind__value?: InputMaybe<Scalars["String"]>;
  kind__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  message__is_protected?: InputMaybe<Scalars["Boolean"]>;
  message__is_visible?: InputMaybe<Scalars["Boolean"]>;
  message__owner__id?: InputMaybe<Scalars["ID"]>;
  message__source__id?: InputMaybe<Scalars["ID"]>;
  message__value?: InputMaybe<Scalars["String"]>;
  message__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  origin__is_protected?: InputMaybe<Scalars["Boolean"]>;
  origin__is_visible?: InputMaybe<Scalars["Boolean"]>;
  origin__owner__id?: InputMaybe<Scalars["ID"]>;
  origin__source__id?: InputMaybe<Scalars["ID"]>;
  origin__value?: InputMaybe<Scalars["String"]>;
  origin__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  severity__is_protected?: InputMaybe<Scalars["Boolean"]>;
  severity__is_visible?: InputMaybe<Scalars["Boolean"]>;
  severity__owner__id?: InputMaybe<Scalars["ID"]>;
  severity__source__id?: InputMaybe<Scalars["ID"]>;
  severity__value?: InputMaybe<Scalars["String"]>;
  severity__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

/** A validator related to the artifacts */
export type CoreArtifactValidatorMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A validator related to the artifacts */
export type CoreArtifactValidatorSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A validator related to the artifacts */
export type CoreArtifactValidatorCreate = {
  __typename?: "CoreArtifactValidatorCreate";
  object?: Maybe<CoreArtifactValidator>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreArtifactValidatorCreateInput = {
  checks?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  completed_at?: InputMaybe<TextAttributeInput>;
  conclusion?: InputMaybe<TextAttributeInput>;
  definition: RelatedNodeInput;
  id?: InputMaybe<Scalars["String"]>;
  label?: InputMaybe<TextAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  proposed_change: RelatedNodeInput;
  started_at?: InputMaybe<TextAttributeInput>;
  state?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** A validator related to the artifacts */
export type CoreArtifactValidatorDelete = {
  __typename?: "CoreArtifactValidatorDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A validator related to the artifacts */
export type CoreArtifactValidatorUpdate = {
  __typename?: "CoreArtifactValidatorUpdate";
  object?: Maybe<CoreArtifactValidator>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreArtifactValidatorUpdateInput = {
  checks?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  completed_at?: InputMaybe<TextAttributeInput>;
  conclusion?: InputMaybe<TextAttributeInput>;
  definition?: InputMaybe<RelatedNodeInput>;
  id: Scalars["String"];
  label?: InputMaybe<TextAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  proposed_change?: InputMaybe<RelatedNodeInput>;
  started_at?: InputMaybe<TextAttributeInput>;
  state?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** A validator related to the artifacts */
export type CoreArtifactValidatorUpsert = {
  __typename?: "CoreArtifactValidatorUpsert";
  object?: Maybe<CoreArtifactValidator>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A comment on proposed change */
export type CoreChangeComment = CoreComment &
  CoreNode & {
    __typename?: "CoreChangeComment";
    _updated_at?: Maybe<Scalars["DateTime"]>;
    change?: Maybe<NestedEdgedCoreProposedChange>;
    created_at?: Maybe<TextAttribute>;
    created_by?: Maybe<NestedEdgedCoreAccount>;
    display_label?: Maybe<Scalars["String"]>;
    id: Scalars["String"];
    member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    text: TextAttribute;
  };

/** A comment on proposed change */
export type CoreChangeCommentMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A comment on proposed change */
export type CoreChangeCommentSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A comment on proposed change */
export type CoreChangeCommentCreate = {
  __typename?: "CoreChangeCommentCreate";
  object?: Maybe<CoreChangeComment>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreChangeCommentCreateInput = {
  change: RelatedNodeInput;
  created_at?: InputMaybe<TextAttributeInput>;
  created_by?: InputMaybe<RelatedNodeInput>;
  id?: InputMaybe<Scalars["String"]>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  text: TextAttributeInput;
};

/** A comment on proposed change */
export type CoreChangeCommentDelete = {
  __typename?: "CoreChangeCommentDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A comment on proposed change */
export type CoreChangeCommentUpdate = {
  __typename?: "CoreChangeCommentUpdate";
  object?: Maybe<CoreChangeComment>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreChangeCommentUpdateInput = {
  change?: InputMaybe<RelatedNodeInput>;
  created_at?: InputMaybe<TextAttributeInput>;
  created_by?: InputMaybe<RelatedNodeInput>;
  id: Scalars["String"];
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  text?: InputMaybe<TextAttributeInput>;
};

/** A comment on proposed change */
export type CoreChangeCommentUpsert = {
  __typename?: "CoreChangeCommentUpsert";
  object?: Maybe<CoreChangeComment>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A thread on proposed change */
export type CoreChangeThread = CoreNode &
  CoreThread & {
    __typename?: "CoreChangeThread";
    _updated_at?: Maybe<Scalars["DateTime"]>;
    change?: Maybe<NestedEdgedCoreProposedChange>;
    comments?: Maybe<NestedPaginatedCoreThreadComment>;
    created_at?: Maybe<TextAttribute>;
    created_by?: Maybe<NestedEdgedCoreAccount>;
    display_label?: Maybe<Scalars["String"]>;
    id: Scalars["String"];
    label?: Maybe<TextAttribute>;
    member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    resolved?: Maybe<CheckboxAttribute>;
    subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  };

/** A thread on proposed change */
export type CoreChangeThreadCommentsArgs = {
  created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  created_at__source__id?: InputMaybe<Scalars["ID"]>;
  created_at__value?: InputMaybe<Scalars["String"]>;
  created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  offset?: InputMaybe<Scalars["Int"]>;
  text__is_protected?: InputMaybe<Scalars["Boolean"]>;
  text__is_visible?: InputMaybe<Scalars["Boolean"]>;
  text__owner__id?: InputMaybe<Scalars["ID"]>;
  text__source__id?: InputMaybe<Scalars["ID"]>;
  text__value?: InputMaybe<Scalars["String"]>;
  text__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

/** A thread on proposed change */
export type CoreChangeThreadMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A thread on proposed change */
export type CoreChangeThreadSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A thread on proposed change */
export type CoreChangeThreadCreate = {
  __typename?: "CoreChangeThreadCreate";
  object?: Maybe<CoreChangeThread>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreChangeThreadCreateInput = {
  change: RelatedNodeInput;
  comments?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  created_at?: InputMaybe<TextAttributeInput>;
  created_by?: InputMaybe<RelatedNodeInput>;
  id?: InputMaybe<Scalars["String"]>;
  label?: InputMaybe<TextAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  resolved?: InputMaybe<CheckboxAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** A thread on proposed change */
export type CoreChangeThreadDelete = {
  __typename?: "CoreChangeThreadDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A thread on proposed change */
export type CoreChangeThreadUpdate = {
  __typename?: "CoreChangeThreadUpdate";
  object?: Maybe<CoreChangeThread>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreChangeThreadUpdateInput = {
  change?: InputMaybe<RelatedNodeInput>;
  comments?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  created_at?: InputMaybe<TextAttributeInput>;
  created_by?: InputMaybe<RelatedNodeInput>;
  id: Scalars["String"];
  label?: InputMaybe<TextAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  resolved?: InputMaybe<CheckboxAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** A thread on proposed change */
export type CoreChangeThreadUpsert = {
  __typename?: "CoreChangeThreadUpsert";
  object?: Maybe<CoreChangeThread>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreCheck = {
  conclusion?: Maybe<TextAttribute>;
  created_at?: Maybe<TextAttribute>;
  display_label?: Maybe<Scalars["String"]>;
  /** Unique identifier */
  id?: Maybe<Scalars["String"]>;
  kind: TextAttribute;
  label?: Maybe<TextAttribute>;
  member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  message?: Maybe<TextAttribute>;
  name?: Maybe<TextAttribute>;
  origin: TextAttribute;
  severity?: Maybe<TextAttribute>;
  subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  validator?: Maybe<NestedEdgedCoreValidator>;
};

export type CoreCheckMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

export type CoreCheckSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

export type CoreCheckDefinition = CoreNode &
  CoreTaskTarget & {
    __typename?: "CoreCheckDefinition";
    _updated_at?: Maybe<Scalars["DateTime"]>;
    class_name: TextAttribute;
    description?: Maybe<TextAttribute>;
    display_label?: Maybe<Scalars["String"]>;
    file_path: TextAttribute;
    id: Scalars["String"];
    member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    name: TextAttribute;
    parameters?: Maybe<JsonAttribute>;
    query?: Maybe<NestedEdgedCoreGraphQlQuery>;
    repository?: Maybe<NestedEdgedCoreGenericRepository>;
    subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    tags?: Maybe<NestedPaginatedBuiltinTag>;
    targets?: Maybe<NestedEdgedCoreGroup>;
    timeout?: Maybe<NumberAttribute>;
  };

export type CoreCheckDefinitionMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

export type CoreCheckDefinitionSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

export type CoreCheckDefinitionTagsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

export type CoreCheckDefinitionCreate = {
  __typename?: "CoreCheckDefinitionCreate";
  object?: Maybe<CoreCheckDefinition>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreCheckDefinitionCreateInput = {
  class_name: TextAttributeInput;
  description?: InputMaybe<TextAttributeInput>;
  file_path: TextAttributeInput;
  id?: InputMaybe<Scalars["String"]>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name: TextAttributeInput;
  parameters?: InputMaybe<JsonAttributeInput>;
  query?: InputMaybe<RelatedNodeInput>;
  repository: RelatedNodeInput;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  targets?: InputMaybe<RelatedNodeInput>;
  timeout?: InputMaybe<NumberAttributeInput>;
};

export type CoreCheckDefinitionDelete = {
  __typename?: "CoreCheckDefinitionDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreCheckDefinitionUpdate = {
  __typename?: "CoreCheckDefinitionUpdate";
  object?: Maybe<CoreCheckDefinition>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreCheckDefinitionUpdateInput = {
  class_name?: InputMaybe<TextAttributeInput>;
  description?: InputMaybe<TextAttributeInput>;
  file_path?: InputMaybe<TextAttributeInput>;
  id: Scalars["String"];
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name?: InputMaybe<TextAttributeInput>;
  parameters?: InputMaybe<JsonAttributeInput>;
  query?: InputMaybe<RelatedNodeInput>;
  repository?: InputMaybe<RelatedNodeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  targets?: InputMaybe<RelatedNodeInput>;
  timeout?: InputMaybe<NumberAttributeInput>;
};

export type CoreCheckDefinitionUpsert = {
  __typename?: "CoreCheckDefinitionUpsert";
  object?: Maybe<CoreCheckDefinition>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A comment on a Proposed Change */
export type CoreComment = {
  created_at?: Maybe<TextAttribute>;
  created_by?: Maybe<NestedEdgedCoreAccount>;
  display_label?: Maybe<Scalars["String"]>;
  /** Unique identifier */
  id?: Maybe<Scalars["String"]>;
  member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  text: TextAttribute;
};

/** A comment on a Proposed Change */
export type CoreCommentMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A comment on a Proposed Change */
export type CoreCommentSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A webhook that connects to an external integration */
export type CoreCustomWebhook = CoreNode &
  CoreTaskTarget &
  CoreWebhook & {
    __typename?: "CoreCustomWebhook";
    _updated_at?: Maybe<Scalars["DateTime"]>;
    description?: Maybe<TextAttribute>;
    display_label?: Maybe<Scalars["String"]>;
    id: Scalars["String"];
    member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    name: TextAttribute;
    subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    transformation?: Maybe<NestedEdgedCoreTransformPython>;
    url: TextAttribute;
    validate_certificates?: Maybe<CheckboxAttribute>;
  };

/** A webhook that connects to an external integration */
export type CoreCustomWebhookMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A webhook that connects to an external integration */
export type CoreCustomWebhookSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A webhook that connects to an external integration */
export type CoreCustomWebhookCreate = {
  __typename?: "CoreCustomWebhookCreate";
  object?: Maybe<CoreCustomWebhook>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreCustomWebhookCreateInput = {
  description?: InputMaybe<TextAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name: TextAttributeInput;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  transformation?: InputMaybe<RelatedNodeInput>;
  url: TextAttributeInput;
  validate_certificates?: InputMaybe<CheckboxAttributeInput>;
};

/** A webhook that connects to an external integration */
export type CoreCustomWebhookDelete = {
  __typename?: "CoreCustomWebhookDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A webhook that connects to an external integration */
export type CoreCustomWebhookUpdate = {
  __typename?: "CoreCustomWebhookUpdate";
  object?: Maybe<CoreCustomWebhook>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreCustomWebhookUpdateInput = {
  description?: InputMaybe<TextAttributeInput>;
  id: Scalars["String"];
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  transformation?: InputMaybe<RelatedNodeInput>;
  url?: InputMaybe<TextAttributeInput>;
  validate_certificates?: InputMaybe<CheckboxAttributeInput>;
};

/** A webhook that connects to an external integration */
export type CoreCustomWebhookUpsert = {
  __typename?: "CoreCustomWebhookUpsert";
  object?: Maybe<CoreCustomWebhook>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A check related to some Data */
export type CoreDataCheck = CoreCheck &
  CoreNode & {
    __typename?: "CoreDataCheck";
    _updated_at?: Maybe<Scalars["DateTime"]>;
    conclusion?: Maybe<TextAttribute>;
    conflicts: JsonAttribute;
    created_at?: Maybe<TextAttribute>;
    display_label?: Maybe<Scalars["String"]>;
    id: Scalars["String"];
    keep_branch?: Maybe<TextAttribute>;
    kind: TextAttribute;
    label?: Maybe<TextAttribute>;
    member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    message?: Maybe<TextAttribute>;
    name?: Maybe<TextAttribute>;
    origin: TextAttribute;
    severity?: Maybe<TextAttribute>;
    subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    validator?: Maybe<NestedEdgedCoreValidator>;
  };

/** A check related to some Data */
export type CoreDataCheckMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A check related to some Data */
export type CoreDataCheckSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A check related to some Data */
export type CoreDataCheckCreate = {
  __typename?: "CoreDataCheckCreate";
  object?: Maybe<CoreDataCheck>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreDataCheckCreateInput = {
  conclusion?: InputMaybe<TextAttributeInput>;
  conflicts: JsonAttributeInput;
  created_at?: InputMaybe<TextAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  keep_branch?: InputMaybe<TextAttributeInput>;
  kind: TextAttributeInput;
  label?: InputMaybe<TextAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  message?: InputMaybe<TextAttributeInput>;
  name?: InputMaybe<TextAttributeInput>;
  origin: TextAttributeInput;
  severity?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  validator: RelatedNodeInput;
};

/** A check related to some Data */
export type CoreDataCheckDelete = {
  __typename?: "CoreDataCheckDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A check related to some Data */
export type CoreDataCheckUpdate = {
  __typename?: "CoreDataCheckUpdate";
  object?: Maybe<CoreDataCheck>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreDataCheckUpdateInput = {
  conclusion?: InputMaybe<TextAttributeInput>;
  conflicts?: InputMaybe<JsonAttributeInput>;
  created_at?: InputMaybe<TextAttributeInput>;
  id: Scalars["String"];
  keep_branch?: InputMaybe<TextAttributeInput>;
  kind?: InputMaybe<TextAttributeInput>;
  label?: InputMaybe<TextAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  message?: InputMaybe<TextAttributeInput>;
  name?: InputMaybe<TextAttributeInput>;
  origin?: InputMaybe<TextAttributeInput>;
  severity?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  validator?: InputMaybe<RelatedNodeInput>;
};

/** A check related to some Data */
export type CoreDataCheckUpsert = {
  __typename?: "CoreDataCheckUpsert";
  object?: Maybe<CoreDataCheck>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A check to validate the data integrity between two branches */
export type CoreDataValidator = CoreNode &
  CoreValidator & {
    __typename?: "CoreDataValidator";
    _updated_at?: Maybe<Scalars["DateTime"]>;
    checks?: Maybe<NestedPaginatedCoreCheck>;
    completed_at?: Maybe<TextAttribute>;
    conclusion?: Maybe<TextAttribute>;
    display_label?: Maybe<Scalars["String"]>;
    id: Scalars["String"];
    label?: Maybe<TextAttribute>;
    member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    proposed_change?: Maybe<NestedEdgedCoreProposedChange>;
    started_at?: Maybe<TextAttribute>;
    state?: Maybe<TextAttribute>;
    subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  };

/** A check to validate the data integrity between two branches */
export type CoreDataValidatorChecksArgs = {
  conclusion__is_protected?: InputMaybe<Scalars["Boolean"]>;
  conclusion__is_visible?: InputMaybe<Scalars["Boolean"]>;
  conclusion__owner__id?: InputMaybe<Scalars["ID"]>;
  conclusion__source__id?: InputMaybe<Scalars["ID"]>;
  conclusion__value?: InputMaybe<Scalars["String"]>;
  conclusion__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  created_at__source__id?: InputMaybe<Scalars["ID"]>;
  created_at__value?: InputMaybe<Scalars["String"]>;
  created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  kind__is_protected?: InputMaybe<Scalars["Boolean"]>;
  kind__is_visible?: InputMaybe<Scalars["Boolean"]>;
  kind__owner__id?: InputMaybe<Scalars["ID"]>;
  kind__source__id?: InputMaybe<Scalars["ID"]>;
  kind__value?: InputMaybe<Scalars["String"]>;
  kind__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  message__is_protected?: InputMaybe<Scalars["Boolean"]>;
  message__is_visible?: InputMaybe<Scalars["Boolean"]>;
  message__owner__id?: InputMaybe<Scalars["ID"]>;
  message__source__id?: InputMaybe<Scalars["ID"]>;
  message__value?: InputMaybe<Scalars["String"]>;
  message__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  origin__is_protected?: InputMaybe<Scalars["Boolean"]>;
  origin__is_visible?: InputMaybe<Scalars["Boolean"]>;
  origin__owner__id?: InputMaybe<Scalars["ID"]>;
  origin__source__id?: InputMaybe<Scalars["ID"]>;
  origin__value?: InputMaybe<Scalars["String"]>;
  origin__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  severity__is_protected?: InputMaybe<Scalars["Boolean"]>;
  severity__is_visible?: InputMaybe<Scalars["Boolean"]>;
  severity__owner__id?: InputMaybe<Scalars["ID"]>;
  severity__source__id?: InputMaybe<Scalars["ID"]>;
  severity__value?: InputMaybe<Scalars["String"]>;
  severity__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

/** A check to validate the data integrity between two branches */
export type CoreDataValidatorMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A check to validate the data integrity between two branches */
export type CoreDataValidatorSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A check to validate the data integrity between two branches */
export type CoreDataValidatorCreate = {
  __typename?: "CoreDataValidatorCreate";
  object?: Maybe<CoreDataValidator>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreDataValidatorCreateInput = {
  checks?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  completed_at?: InputMaybe<TextAttributeInput>;
  conclusion?: InputMaybe<TextAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  label?: InputMaybe<TextAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  proposed_change: RelatedNodeInput;
  started_at?: InputMaybe<TextAttributeInput>;
  state?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** A check to validate the data integrity between two branches */
export type CoreDataValidatorDelete = {
  __typename?: "CoreDataValidatorDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A check to validate the data integrity between two branches */
export type CoreDataValidatorUpdate = {
  __typename?: "CoreDataValidatorUpdate";
  object?: Maybe<CoreDataValidator>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreDataValidatorUpdateInput = {
  checks?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  completed_at?: InputMaybe<TextAttributeInput>;
  conclusion?: InputMaybe<TextAttributeInput>;
  id: Scalars["String"];
  label?: InputMaybe<TextAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  proposed_change?: InputMaybe<RelatedNodeInput>;
  started_at?: InputMaybe<TextAttributeInput>;
  state?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** A check to validate the data integrity between two branches */
export type CoreDataValidatorUpsert = {
  __typename?: "CoreDataValidatorUpsert";
  object?: Maybe<CoreDataValidator>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A check related to a file in a Git Repository */
export type CoreFileCheck = CoreCheck &
  CoreNode & {
    __typename?: "CoreFileCheck";
    _updated_at?: Maybe<Scalars["DateTime"]>;
    commit?: Maybe<TextAttribute>;
    conclusion?: Maybe<TextAttribute>;
    created_at?: Maybe<TextAttribute>;
    display_label?: Maybe<Scalars["String"]>;
    files?: Maybe<ListAttribute>;
    id: Scalars["String"];
    kind: TextAttribute;
    label?: Maybe<TextAttribute>;
    member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    message?: Maybe<TextAttribute>;
    name?: Maybe<TextAttribute>;
    origin: TextAttribute;
    severity?: Maybe<TextAttribute>;
    subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    validator?: Maybe<NestedEdgedCoreValidator>;
  };

/** A check related to a file in a Git Repository */
export type CoreFileCheckMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A check related to a file in a Git Repository */
export type CoreFileCheckSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A check related to a file in a Git Repository */
export type CoreFileCheckCreate = {
  __typename?: "CoreFileCheckCreate";
  object?: Maybe<CoreFileCheck>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreFileCheckCreateInput = {
  commit?: InputMaybe<TextAttributeInput>;
  conclusion?: InputMaybe<TextAttributeInput>;
  created_at?: InputMaybe<TextAttributeInput>;
  files?: InputMaybe<ListAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  kind: TextAttributeInput;
  label?: InputMaybe<TextAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  message?: InputMaybe<TextAttributeInput>;
  name?: InputMaybe<TextAttributeInput>;
  origin: TextAttributeInput;
  severity?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  validator: RelatedNodeInput;
};

/** A check related to a file in a Git Repository */
export type CoreFileCheckDelete = {
  __typename?: "CoreFileCheckDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A check related to a file in a Git Repository */
export type CoreFileCheckUpdate = {
  __typename?: "CoreFileCheckUpdate";
  object?: Maybe<CoreFileCheck>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreFileCheckUpdateInput = {
  commit?: InputMaybe<TextAttributeInput>;
  conclusion?: InputMaybe<TextAttributeInput>;
  created_at?: InputMaybe<TextAttributeInput>;
  files?: InputMaybe<ListAttributeInput>;
  id: Scalars["String"];
  kind?: InputMaybe<TextAttributeInput>;
  label?: InputMaybe<TextAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  message?: InputMaybe<TextAttributeInput>;
  name?: InputMaybe<TextAttributeInput>;
  origin?: InputMaybe<TextAttributeInput>;
  severity?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  validator?: InputMaybe<RelatedNodeInput>;
};

/** A check related to a file in a Git Repository */
export type CoreFileCheckUpsert = {
  __typename?: "CoreFileCheckUpsert";
  object?: Maybe<CoreFileCheck>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A thread related to a file on a proposed change */
export type CoreFileThread = CoreNode &
  CoreThread & {
    __typename?: "CoreFileThread";
    _updated_at?: Maybe<Scalars["DateTime"]>;
    change?: Maybe<NestedEdgedCoreProposedChange>;
    comments?: Maybe<NestedPaginatedCoreThreadComment>;
    commit?: Maybe<TextAttribute>;
    created_at?: Maybe<TextAttribute>;
    created_by?: Maybe<NestedEdgedCoreAccount>;
    display_label?: Maybe<Scalars["String"]>;
    file?: Maybe<TextAttribute>;
    id: Scalars["String"];
    label?: Maybe<TextAttribute>;
    line_number?: Maybe<NumberAttribute>;
    member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    repository?: Maybe<NestedEdgedCoreRepository>;
    resolved?: Maybe<CheckboxAttribute>;
    subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  };

/** A thread related to a file on a proposed change */
export type CoreFileThreadCommentsArgs = {
  created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  created_at__source__id?: InputMaybe<Scalars["ID"]>;
  created_at__value?: InputMaybe<Scalars["String"]>;
  created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  offset?: InputMaybe<Scalars["Int"]>;
  text__is_protected?: InputMaybe<Scalars["Boolean"]>;
  text__is_visible?: InputMaybe<Scalars["Boolean"]>;
  text__owner__id?: InputMaybe<Scalars["ID"]>;
  text__source__id?: InputMaybe<Scalars["ID"]>;
  text__value?: InputMaybe<Scalars["String"]>;
  text__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

/** A thread related to a file on a proposed change */
export type CoreFileThreadMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A thread related to a file on a proposed change */
export type CoreFileThreadSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A thread related to a file on a proposed change */
export type CoreFileThreadCreate = {
  __typename?: "CoreFileThreadCreate";
  object?: Maybe<CoreFileThread>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreFileThreadCreateInput = {
  change: RelatedNodeInput;
  comments?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  commit?: InputMaybe<TextAttributeInput>;
  created_at?: InputMaybe<TextAttributeInput>;
  created_by?: InputMaybe<RelatedNodeInput>;
  file?: InputMaybe<TextAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  label?: InputMaybe<TextAttributeInput>;
  line_number?: InputMaybe<NumberAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  repository: RelatedNodeInput;
  resolved?: InputMaybe<CheckboxAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** A thread related to a file on a proposed change */
export type CoreFileThreadDelete = {
  __typename?: "CoreFileThreadDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A thread related to a file on a proposed change */
export type CoreFileThreadUpdate = {
  __typename?: "CoreFileThreadUpdate";
  object?: Maybe<CoreFileThread>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreFileThreadUpdateInput = {
  change?: InputMaybe<RelatedNodeInput>;
  comments?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  commit?: InputMaybe<TextAttributeInput>;
  created_at?: InputMaybe<TextAttributeInput>;
  created_by?: InputMaybe<RelatedNodeInput>;
  file?: InputMaybe<TextAttributeInput>;
  id: Scalars["String"];
  label?: InputMaybe<TextAttributeInput>;
  line_number?: InputMaybe<NumberAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  repository?: InputMaybe<RelatedNodeInput>;
  resolved?: InputMaybe<CheckboxAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** A thread related to a file on a proposed change */
export type CoreFileThreadUpsert = {
  __typename?: "CoreFileThreadUpsert";
  object?: Maybe<CoreFileThread>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A Git Repository integrated with Infrahub */
export type CoreGenericRepository = {
  checks?: Maybe<NestedPaginatedCoreCheckDefinition>;
  description?: Maybe<TextAttribute>;
  display_label?: Maybe<Scalars["String"]>;
  /** Unique identifier */
  id?: Maybe<Scalars["String"]>;
  location: TextAttribute;
  member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  name: TextAttribute;
  password?: Maybe<TextAttribute>;
  queries?: Maybe<NestedPaginatedCoreGraphQlQuery>;
  subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  tags?: Maybe<NestedPaginatedBuiltinTag>;
  transformations?: Maybe<NestedPaginatedCoreTransformation>;
  username?: Maybe<TextAttribute>;
};

/** A Git Repository integrated with Infrahub */
export type CoreGenericRepositoryChecksArgs = {
  class_name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  class_name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  class_name__owner__id?: InputMaybe<Scalars["ID"]>;
  class_name__source__id?: InputMaybe<Scalars["ID"]>;
  class_name__value?: InputMaybe<Scalars["String"]>;
  class_name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  file_path__is_protected?: InputMaybe<Scalars["Boolean"]>;
  file_path__is_visible?: InputMaybe<Scalars["Boolean"]>;
  file_path__owner__id?: InputMaybe<Scalars["ID"]>;
  file_path__source__id?: InputMaybe<Scalars["ID"]>;
  file_path__value?: InputMaybe<Scalars["String"]>;
  file_path__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  parameters__is_protected?: InputMaybe<Scalars["Boolean"]>;
  parameters__is_visible?: InputMaybe<Scalars["Boolean"]>;
  parameters__owner__id?: InputMaybe<Scalars["ID"]>;
  parameters__source__id?: InputMaybe<Scalars["ID"]>;
  parameters__value?: InputMaybe<Scalars["GenericScalar"]>;
  parameters__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  timeout__is_protected?: InputMaybe<Scalars["Boolean"]>;
  timeout__is_visible?: InputMaybe<Scalars["Boolean"]>;
  timeout__owner__id?: InputMaybe<Scalars["ID"]>;
  timeout__source__id?: InputMaybe<Scalars["ID"]>;
  timeout__value?: InputMaybe<Scalars["Int"]>;
  timeout__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
};

/** A Git Repository integrated with Infrahub */
export type CoreGenericRepositoryMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A Git Repository integrated with Infrahub */
export type CoreGenericRepositoryQueriesArgs = {
  depth__is_protected?: InputMaybe<Scalars["Boolean"]>;
  depth__is_visible?: InputMaybe<Scalars["Boolean"]>;
  depth__owner__id?: InputMaybe<Scalars["ID"]>;
  depth__source__id?: InputMaybe<Scalars["ID"]>;
  depth__value?: InputMaybe<Scalars["Int"]>;
  depth__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  height__is_protected?: InputMaybe<Scalars["Boolean"]>;
  height__is_visible?: InputMaybe<Scalars["Boolean"]>;
  height__owner__id?: InputMaybe<Scalars["ID"]>;
  height__source__id?: InputMaybe<Scalars["ID"]>;
  height__value?: InputMaybe<Scalars["Int"]>;
  height__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  models__is_protected?: InputMaybe<Scalars["Boolean"]>;
  models__is_visible?: InputMaybe<Scalars["Boolean"]>;
  models__owner__id?: InputMaybe<Scalars["ID"]>;
  models__source__id?: InputMaybe<Scalars["ID"]>;
  models__value?: InputMaybe<Scalars["GenericScalar"]>;
  models__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  operations__is_protected?: InputMaybe<Scalars["Boolean"]>;
  operations__is_visible?: InputMaybe<Scalars["Boolean"]>;
  operations__owner__id?: InputMaybe<Scalars["ID"]>;
  operations__source__id?: InputMaybe<Scalars["ID"]>;
  operations__value?: InputMaybe<Scalars["GenericScalar"]>;
  operations__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  query__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__owner__id?: InputMaybe<Scalars["ID"]>;
  query__source__id?: InputMaybe<Scalars["ID"]>;
  query__value?: InputMaybe<Scalars["String"]>;
  query__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  variables__is_protected?: InputMaybe<Scalars["Boolean"]>;
  variables__is_visible?: InputMaybe<Scalars["Boolean"]>;
  variables__owner__id?: InputMaybe<Scalars["ID"]>;
  variables__source__id?: InputMaybe<Scalars["ID"]>;
  variables__value?: InputMaybe<Scalars["GenericScalar"]>;
  variables__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
};

/** A Git Repository integrated with Infrahub */
export type CoreGenericRepositorySubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A Git Repository integrated with Infrahub */
export type CoreGenericRepositoryTagsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A Git Repository integrated with Infrahub */
export type CoreGenericRepositoryTransformationsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  timeout__is_protected?: InputMaybe<Scalars["Boolean"]>;
  timeout__is_visible?: InputMaybe<Scalars["Boolean"]>;
  timeout__owner__id?: InputMaybe<Scalars["ID"]>;
  timeout__source__id?: InputMaybe<Scalars["ID"]>;
  timeout__value?: InputMaybe<Scalars["Int"]>;
  timeout__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
};

/** A pre-defined GraphQL Query */
export type CoreGraphQlQuery = CoreNode & {
  __typename?: "CoreGraphQLQuery";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  /** number of nested levels in the query */
  depth?: Maybe<NumberAttribute>;
  description?: Maybe<TextAttribute>;
  display_label?: Maybe<Scalars["String"]>;
  /** total number of fields requested in the query */
  height?: Maybe<NumberAttribute>;
  id: Scalars["String"];
  member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  /** List of models associated with this query */
  models?: Maybe<ListAttribute>;
  name: TextAttribute;
  /** Operations in use in the query, valid operations: 'query', 'mutation' or 'subscription' */
  operations?: Maybe<ListAttribute>;
  query: TextAttribute;
  repository?: Maybe<NestedEdgedCoreGenericRepository>;
  subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  tags?: Maybe<NestedPaginatedBuiltinTag>;
  /** variables in use in the query */
  variables?: Maybe<JsonAttribute>;
};

/** A pre-defined GraphQL Query */
export type CoreGraphQlQueryMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A pre-defined GraphQL Query */
export type CoreGraphQlQuerySubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A pre-defined GraphQL Query */
export type CoreGraphQlQueryTagsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A pre-defined GraphQL Query */
export type CoreGraphQlQueryCreate = {
  __typename?: "CoreGraphQLQueryCreate";
  object?: Maybe<CoreGraphQlQuery>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreGraphQlQueryCreateInput = {
  description?: InputMaybe<TextAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name: TextAttributeInput;
  query: TextAttributeInput;
  repository?: InputMaybe<RelatedNodeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  /** variables in use in the query */
  variables?: InputMaybe<JsonAttributeInput>;
};

/** A pre-defined GraphQL Query */
export type CoreGraphQlQueryDelete = {
  __typename?: "CoreGraphQLQueryDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** Group of nodes associated with a given GraphQLQuery. */
export type CoreGraphQlQueryGroup = CoreGroup & {
  __typename?: "CoreGraphQLQueryGroup";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  ancestors?: Maybe<NestedPaginatedCoreGroup>;
  children?: Maybe<NestedPaginatedCoreGroup>;
  descendants?: Maybe<NestedPaginatedCoreGroup>;
  description?: Maybe<TextAttribute>;
  display_label?: Maybe<Scalars["String"]>;
  id: Scalars["String"];
  label?: Maybe<TextAttribute>;
  members?: Maybe<NestedPaginatedCoreNode>;
  name: TextAttribute;
  parameters?: Maybe<JsonAttribute>;
  parent?: Maybe<NestedEdgedCoreGroup>;
  query?: Maybe<NestedEdgedCoreGraphQlQuery>;
  subscribers?: Maybe<NestedPaginatedCoreNode>;
};

/** Group of nodes associated with a given GraphQLQuery. */
export type CoreGraphQlQueryGroupAncestorsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Group of nodes associated with a given GraphQLQuery. */
export type CoreGraphQlQueryGroupChildrenArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  include_descendants?: InputMaybe<Scalars["Boolean"]>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Group of nodes associated with a given GraphQLQuery. */
export type CoreGraphQlQueryGroupDescendantsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Group of nodes associated with a given GraphQLQuery. */
export type CoreGraphQlQueryGroupMembersArgs = {
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  include_descendants?: InputMaybe<Scalars["Boolean"]>;
  limit?: InputMaybe<Scalars["Int"]>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Group of nodes associated with a given GraphQLQuery. */
export type CoreGraphQlQueryGroupSubscribersArgs = {
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  include_descendants?: InputMaybe<Scalars["Boolean"]>;
  limit?: InputMaybe<Scalars["Int"]>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Group of nodes associated with a given GraphQLQuery. */
export type CoreGraphQlQueryGroupCreate = {
  __typename?: "CoreGraphQLQueryGroupCreate";
  object?: Maybe<CoreGraphQlQueryGroup>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreGraphQlQueryGroupCreateInput = {
  children?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  description?: InputMaybe<TextAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  label?: InputMaybe<TextAttributeInput>;
  members?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name: TextAttributeInput;
  parameters?: InputMaybe<JsonAttributeInput>;
  parent?: InputMaybe<RelatedNodeInput>;
  query: RelatedNodeInput;
  subscribers?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** Group of nodes associated with a given GraphQLQuery. */
export type CoreGraphQlQueryGroupDelete = {
  __typename?: "CoreGraphQLQueryGroupDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** Group of nodes associated with a given GraphQLQuery. */
export type CoreGraphQlQueryGroupUpdate = {
  __typename?: "CoreGraphQLQueryGroupUpdate";
  object?: Maybe<CoreGraphQlQueryGroup>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreGraphQlQueryGroupUpdateInput = {
  children?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  description?: InputMaybe<TextAttributeInput>;
  id: Scalars["String"];
  label?: InputMaybe<TextAttributeInput>;
  members?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name?: InputMaybe<TextAttributeInput>;
  parameters?: InputMaybe<JsonAttributeInput>;
  parent?: InputMaybe<RelatedNodeInput>;
  query?: InputMaybe<RelatedNodeInput>;
  subscribers?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** Group of nodes associated with a given GraphQLQuery. */
export type CoreGraphQlQueryGroupUpsert = {
  __typename?: "CoreGraphQLQueryGroupUpsert";
  object?: Maybe<CoreGraphQlQueryGroup>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A pre-defined GraphQL Query */
export type CoreGraphQlQueryUpdate = {
  __typename?: "CoreGraphQLQueryUpdate";
  object?: Maybe<CoreGraphQlQuery>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreGraphQlQueryUpdateInput = {
  description?: InputMaybe<TextAttributeInput>;
  id: Scalars["String"];
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name?: InputMaybe<TextAttributeInput>;
  query?: InputMaybe<TextAttributeInput>;
  repository?: InputMaybe<RelatedNodeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  /** variables in use in the query */
  variables?: InputMaybe<JsonAttributeInput>;
};

/** A pre-defined GraphQL Query */
export type CoreGraphQlQueryUpsert = {
  __typename?: "CoreGraphQLQueryUpsert";
  object?: Maybe<CoreGraphQlQuery>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** Generic Group Object. */
export type CoreGroup = {
  description?: Maybe<TextAttribute>;
  display_label?: Maybe<Scalars["String"]>;
  /** Unique identifier */
  id?: Maybe<Scalars["String"]>;
  label?: Maybe<TextAttribute>;
  members?: Maybe<NestedPaginatedCoreNode>;
  name: TextAttribute;
  subscribers?: Maybe<NestedPaginatedCoreNode>;
};

/** Generic Group Object. */
export type CoreGroupMembersArgs = {
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  include_descendants?: InputMaybe<Scalars["Boolean"]>;
  limit?: InputMaybe<Scalars["Int"]>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Generic Group Object. */
export type CoreGroupSubscribersArgs = {
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  include_descendants?: InputMaybe<Scalars["Boolean"]>;
  limit?: InputMaybe<Scalars["Int"]>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Base Node in Infrahub. */
export type CoreNode = {
  display_label?: Maybe<Scalars["String"]>;
  /** Unique identifier */
  id?: Maybe<Scalars["String"]>;
  member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
};

/** Base Node in Infrahub. */
export type CoreNodeMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Base Node in Infrahub. */
export type CoreNodeSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A thread related to an object on a proposed change */
export type CoreObjectThread = CoreNode &
  CoreThread & {
    __typename?: "CoreObjectThread";
    _updated_at?: Maybe<Scalars["DateTime"]>;
    change?: Maybe<NestedEdgedCoreProposedChange>;
    comments?: Maybe<NestedPaginatedCoreThreadComment>;
    created_at?: Maybe<TextAttribute>;
    created_by?: Maybe<NestedEdgedCoreAccount>;
    display_label?: Maybe<Scalars["String"]>;
    id: Scalars["String"];
    label?: Maybe<TextAttribute>;
    member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    object_path: TextAttribute;
    resolved?: Maybe<CheckboxAttribute>;
    subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  };

/** A thread related to an object on a proposed change */
export type CoreObjectThreadCommentsArgs = {
  created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  created_at__source__id?: InputMaybe<Scalars["ID"]>;
  created_at__value?: InputMaybe<Scalars["String"]>;
  created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  offset?: InputMaybe<Scalars["Int"]>;
  text__is_protected?: InputMaybe<Scalars["Boolean"]>;
  text__is_visible?: InputMaybe<Scalars["Boolean"]>;
  text__owner__id?: InputMaybe<Scalars["ID"]>;
  text__source__id?: InputMaybe<Scalars["ID"]>;
  text__value?: InputMaybe<Scalars["String"]>;
  text__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

/** A thread related to an object on a proposed change */
export type CoreObjectThreadMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A thread related to an object on a proposed change */
export type CoreObjectThreadSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A thread related to an object on a proposed change */
export type CoreObjectThreadCreate = {
  __typename?: "CoreObjectThreadCreate";
  object?: Maybe<CoreObjectThread>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreObjectThreadCreateInput = {
  change: RelatedNodeInput;
  comments?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  created_at?: InputMaybe<TextAttributeInput>;
  created_by?: InputMaybe<RelatedNodeInput>;
  id?: InputMaybe<Scalars["String"]>;
  label?: InputMaybe<TextAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  object_path: TextAttributeInput;
  resolved?: InputMaybe<CheckboxAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** A thread related to an object on a proposed change */
export type CoreObjectThreadDelete = {
  __typename?: "CoreObjectThreadDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A thread related to an object on a proposed change */
export type CoreObjectThreadUpdate = {
  __typename?: "CoreObjectThreadUpdate";
  object?: Maybe<CoreObjectThread>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreObjectThreadUpdateInput = {
  change?: InputMaybe<RelatedNodeInput>;
  comments?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  created_at?: InputMaybe<TextAttributeInput>;
  created_by?: InputMaybe<RelatedNodeInput>;
  id: Scalars["String"];
  label?: InputMaybe<TextAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  object_path?: InputMaybe<TextAttributeInput>;
  resolved?: InputMaybe<CheckboxAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** A thread related to an object on a proposed change */
export type CoreObjectThreadUpsert = {
  __typename?: "CoreObjectThreadUpsert";
  object?: Maybe<CoreObjectThread>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** An organization represent a legal entity, a company */
export type CoreOrganization = CoreNode & {
  __typename?: "CoreOrganization";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  description?: Maybe<TextAttribute>;
  display_label?: Maybe<Scalars["String"]>;
  id: Scalars["String"];
  label?: Maybe<TextAttribute>;
  member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  name: TextAttribute;
  subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  tags?: Maybe<NestedPaginatedBuiltinTag>;
};

/** An organization represent a legal entity, a company */
export type CoreOrganizationMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** An organization represent a legal entity, a company */
export type CoreOrganizationSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** An organization represent a legal entity, a company */
export type CoreOrganizationTagsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** An organization represent a legal entity, a company */
export type CoreOrganizationCreate = {
  __typename?: "CoreOrganizationCreate";
  object?: Maybe<CoreOrganization>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreOrganizationCreateInput = {
  description?: InputMaybe<TextAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  label?: InputMaybe<TextAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name: TextAttributeInput;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** An organization represent a legal entity, a company */
export type CoreOrganizationDelete = {
  __typename?: "CoreOrganizationDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** An organization represent a legal entity, a company */
export type CoreOrganizationUpdate = {
  __typename?: "CoreOrganizationUpdate";
  object?: Maybe<CoreOrganization>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreOrganizationUpdateInput = {
  description?: InputMaybe<TextAttributeInput>;
  id: Scalars["String"];
  label?: InputMaybe<TextAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** An organization represent a legal entity, a company */
export type CoreOrganizationUpsert = {
  __typename?: "CoreOrganizationUpsert";
  object?: Maybe<CoreOrganization>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** Metadata related to a proposed change */
export type CoreProposedChange = CoreNode &
  CoreTaskTarget & {
    __typename?: "CoreProposedChange";
    _updated_at?: Maybe<Scalars["DateTime"]>;
    approved_by?: Maybe<NestedPaginatedCoreAccount>;
    comments?: Maybe<NestedPaginatedCoreChangeComment>;
    created_by?: Maybe<NestedEdgedCoreAccount>;
    description?: Maybe<TextAttribute>;
    destination_branch: TextAttribute;
    display_label?: Maybe<Scalars["String"]>;
    id: Scalars["String"];
    member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    name: TextAttribute;
    reviewers?: Maybe<NestedPaginatedCoreAccount>;
    source_branch: TextAttribute;
    state?: Maybe<TextAttribute>;
    subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    threads?: Maybe<NestedPaginatedCoreThread>;
    validations?: Maybe<NestedPaginatedCoreValidator>;
  };

/** Metadata related to a proposed change */
export type CoreProposedChangeApproved_ByArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  password__is_protected?: InputMaybe<Scalars["Boolean"]>;
  password__is_visible?: InputMaybe<Scalars["Boolean"]>;
  password__owner__id?: InputMaybe<Scalars["ID"]>;
  password__source__id?: InputMaybe<Scalars["ID"]>;
  password__value?: InputMaybe<Scalars["String"]>;
  password__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  role__owner__id?: InputMaybe<Scalars["ID"]>;
  role__source__id?: InputMaybe<Scalars["ID"]>;
  role__value?: InputMaybe<Scalars["String"]>;
  role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  type__owner__id?: InputMaybe<Scalars["ID"]>;
  type__source__id?: InputMaybe<Scalars["ID"]>;
  type__value?: InputMaybe<Scalars["String"]>;
  type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

/** Metadata related to a proposed change */
export type CoreProposedChangeCommentsArgs = {
  created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  created_at__source__id?: InputMaybe<Scalars["ID"]>;
  created_at__value?: InputMaybe<Scalars["String"]>;
  created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  offset?: InputMaybe<Scalars["Int"]>;
  text__is_protected?: InputMaybe<Scalars["Boolean"]>;
  text__is_visible?: InputMaybe<Scalars["Boolean"]>;
  text__owner__id?: InputMaybe<Scalars["ID"]>;
  text__source__id?: InputMaybe<Scalars["ID"]>;
  text__value?: InputMaybe<Scalars["String"]>;
  text__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

/** Metadata related to a proposed change */
export type CoreProposedChangeMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Metadata related to a proposed change */
export type CoreProposedChangeReviewersArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  password__is_protected?: InputMaybe<Scalars["Boolean"]>;
  password__is_visible?: InputMaybe<Scalars["Boolean"]>;
  password__owner__id?: InputMaybe<Scalars["ID"]>;
  password__source__id?: InputMaybe<Scalars["ID"]>;
  password__value?: InputMaybe<Scalars["String"]>;
  password__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  role__owner__id?: InputMaybe<Scalars["ID"]>;
  role__source__id?: InputMaybe<Scalars["ID"]>;
  role__value?: InputMaybe<Scalars["String"]>;
  role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  type__owner__id?: InputMaybe<Scalars["ID"]>;
  type__source__id?: InputMaybe<Scalars["ID"]>;
  type__value?: InputMaybe<Scalars["String"]>;
  type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

/** Metadata related to a proposed change */
export type CoreProposedChangeSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Metadata related to a proposed change */
export type CoreProposedChangeThreadsArgs = {
  created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  created_at__source__id?: InputMaybe<Scalars["ID"]>;
  created_at__value?: InputMaybe<Scalars["String"]>;
  created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  offset?: InputMaybe<Scalars["Int"]>;
  resolved__is_protected?: InputMaybe<Scalars["Boolean"]>;
  resolved__is_visible?: InputMaybe<Scalars["Boolean"]>;
  resolved__owner__id?: InputMaybe<Scalars["ID"]>;
  resolved__source__id?: InputMaybe<Scalars["ID"]>;
  resolved__value?: InputMaybe<Scalars["Boolean"]>;
  resolved__values?: InputMaybe<Array<InputMaybe<Scalars["Boolean"]>>>;
};

/** Metadata related to a proposed change */
export type CoreProposedChangeValidationsArgs = {
  completed_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  completed_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  completed_at__owner__id?: InputMaybe<Scalars["ID"]>;
  completed_at__source__id?: InputMaybe<Scalars["ID"]>;
  completed_at__value?: InputMaybe<Scalars["String"]>;
  completed_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  conclusion__is_protected?: InputMaybe<Scalars["Boolean"]>;
  conclusion__is_visible?: InputMaybe<Scalars["Boolean"]>;
  conclusion__owner__id?: InputMaybe<Scalars["ID"]>;
  conclusion__source__id?: InputMaybe<Scalars["ID"]>;
  conclusion__value?: InputMaybe<Scalars["String"]>;
  conclusion__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  offset?: InputMaybe<Scalars["Int"]>;
  started_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  started_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  started_at__owner__id?: InputMaybe<Scalars["ID"]>;
  started_at__source__id?: InputMaybe<Scalars["ID"]>;
  started_at__value?: InputMaybe<Scalars["String"]>;
  started_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  state__is_protected?: InputMaybe<Scalars["Boolean"]>;
  state__is_visible?: InputMaybe<Scalars["Boolean"]>;
  state__owner__id?: InputMaybe<Scalars["ID"]>;
  state__source__id?: InputMaybe<Scalars["ID"]>;
  state__value?: InputMaybe<Scalars["String"]>;
  state__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

/** Metadata related to a proposed change */
export type CoreProposedChangeCreate = {
  __typename?: "CoreProposedChangeCreate";
  object?: Maybe<CoreProposedChange>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreProposedChangeCreateInput = {
  approved_by?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  comments?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  created_by?: InputMaybe<RelatedNodeInput>;
  description?: InputMaybe<TextAttributeInput>;
  destination_branch: TextAttributeInput;
  id?: InputMaybe<Scalars["String"]>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name: TextAttributeInput;
  reviewers?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  source_branch: TextAttributeInput;
  state?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  threads?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  validations?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** Metadata related to a proposed change */
export type CoreProposedChangeDelete = {
  __typename?: "CoreProposedChangeDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** Metadata related to a proposed change */
export type CoreProposedChangeUpdate = {
  __typename?: "CoreProposedChangeUpdate";
  object?: Maybe<CoreProposedChange>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreProposedChangeUpdateInput = {
  approved_by?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  comments?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  created_by?: InputMaybe<RelatedNodeInput>;
  description?: InputMaybe<TextAttributeInput>;
  destination_branch?: InputMaybe<TextAttributeInput>;
  id: Scalars["String"];
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name?: InputMaybe<TextAttributeInput>;
  reviewers?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  source_branch?: InputMaybe<TextAttributeInput>;
  state?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  threads?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  validations?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** Metadata related to a proposed change */
export type CoreProposedChangeUpsert = {
  __typename?: "CoreProposedChangeUpsert";
  object?: Maybe<CoreProposedChange>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A Git Repository integrated with Infrahub, Git-side will not be updated */
export type CoreReadOnlyRepository = CoreGenericRepository &
  CoreNode &
  CoreTaskTarget &
  LineageOwner &
  LineageSource & {
    __typename?: "CoreReadOnlyRepository";
    _updated_at?: Maybe<Scalars["DateTime"]>;
    checks?: Maybe<NestedPaginatedCoreCheckDefinition>;
    commit?: Maybe<TextAttribute>;
    description?: Maybe<TextAttribute>;
    display_label?: Maybe<Scalars["String"]>;
    id: Scalars["String"];
    location: TextAttribute;
    member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    name: TextAttribute;
    password?: Maybe<TextAttribute>;
    queries?: Maybe<NestedPaginatedCoreGraphQlQuery>;
    ref?: Maybe<TextAttribute>;
    subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    tags?: Maybe<NestedPaginatedBuiltinTag>;
    transformations?: Maybe<NestedPaginatedCoreTransformation>;
    username?: Maybe<TextAttribute>;
  };

/** A Git Repository integrated with Infrahub, Git-side will not be updated */
export type CoreReadOnlyRepositoryChecksArgs = {
  class_name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  class_name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  class_name__owner__id?: InputMaybe<Scalars["ID"]>;
  class_name__source__id?: InputMaybe<Scalars["ID"]>;
  class_name__value?: InputMaybe<Scalars["String"]>;
  class_name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  file_path__is_protected?: InputMaybe<Scalars["Boolean"]>;
  file_path__is_visible?: InputMaybe<Scalars["Boolean"]>;
  file_path__owner__id?: InputMaybe<Scalars["ID"]>;
  file_path__source__id?: InputMaybe<Scalars["ID"]>;
  file_path__value?: InputMaybe<Scalars["String"]>;
  file_path__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  parameters__is_protected?: InputMaybe<Scalars["Boolean"]>;
  parameters__is_visible?: InputMaybe<Scalars["Boolean"]>;
  parameters__owner__id?: InputMaybe<Scalars["ID"]>;
  parameters__source__id?: InputMaybe<Scalars["ID"]>;
  parameters__value?: InputMaybe<Scalars["GenericScalar"]>;
  parameters__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  timeout__is_protected?: InputMaybe<Scalars["Boolean"]>;
  timeout__is_visible?: InputMaybe<Scalars["Boolean"]>;
  timeout__owner__id?: InputMaybe<Scalars["ID"]>;
  timeout__source__id?: InputMaybe<Scalars["ID"]>;
  timeout__value?: InputMaybe<Scalars["Int"]>;
  timeout__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
};

/** A Git Repository integrated with Infrahub, Git-side will not be updated */
export type CoreReadOnlyRepositoryMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A Git Repository integrated with Infrahub, Git-side will not be updated */
export type CoreReadOnlyRepositoryQueriesArgs = {
  depth__is_protected?: InputMaybe<Scalars["Boolean"]>;
  depth__is_visible?: InputMaybe<Scalars["Boolean"]>;
  depth__owner__id?: InputMaybe<Scalars["ID"]>;
  depth__source__id?: InputMaybe<Scalars["ID"]>;
  depth__value?: InputMaybe<Scalars["Int"]>;
  depth__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  height__is_protected?: InputMaybe<Scalars["Boolean"]>;
  height__is_visible?: InputMaybe<Scalars["Boolean"]>;
  height__owner__id?: InputMaybe<Scalars["ID"]>;
  height__source__id?: InputMaybe<Scalars["ID"]>;
  height__value?: InputMaybe<Scalars["Int"]>;
  height__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  models__is_protected?: InputMaybe<Scalars["Boolean"]>;
  models__is_visible?: InputMaybe<Scalars["Boolean"]>;
  models__owner__id?: InputMaybe<Scalars["ID"]>;
  models__source__id?: InputMaybe<Scalars["ID"]>;
  models__value?: InputMaybe<Scalars["GenericScalar"]>;
  models__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  operations__is_protected?: InputMaybe<Scalars["Boolean"]>;
  operations__is_visible?: InputMaybe<Scalars["Boolean"]>;
  operations__owner__id?: InputMaybe<Scalars["ID"]>;
  operations__source__id?: InputMaybe<Scalars["ID"]>;
  operations__value?: InputMaybe<Scalars["GenericScalar"]>;
  operations__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  query__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__owner__id?: InputMaybe<Scalars["ID"]>;
  query__source__id?: InputMaybe<Scalars["ID"]>;
  query__value?: InputMaybe<Scalars["String"]>;
  query__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  variables__is_protected?: InputMaybe<Scalars["Boolean"]>;
  variables__is_visible?: InputMaybe<Scalars["Boolean"]>;
  variables__owner__id?: InputMaybe<Scalars["ID"]>;
  variables__source__id?: InputMaybe<Scalars["ID"]>;
  variables__value?: InputMaybe<Scalars["GenericScalar"]>;
  variables__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
};

/** A Git Repository integrated with Infrahub, Git-side will not be updated */
export type CoreReadOnlyRepositorySubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A Git Repository integrated with Infrahub, Git-side will not be updated */
export type CoreReadOnlyRepositoryTagsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A Git Repository integrated with Infrahub, Git-side will not be updated */
export type CoreReadOnlyRepositoryTransformationsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  timeout__is_protected?: InputMaybe<Scalars["Boolean"]>;
  timeout__is_visible?: InputMaybe<Scalars["Boolean"]>;
  timeout__owner__id?: InputMaybe<Scalars["ID"]>;
  timeout__source__id?: InputMaybe<Scalars["ID"]>;
  timeout__value?: InputMaybe<Scalars["Int"]>;
  timeout__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
};

/** A Git Repository integrated with Infrahub, Git-side will not be updated */
export type CoreReadOnlyRepositoryCreate = {
  __typename?: "CoreReadOnlyRepositoryCreate";
  object?: Maybe<CoreReadOnlyRepository>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreReadOnlyRepositoryCreateInput = {
  checks?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  commit?: InputMaybe<TextAttributeInput>;
  description?: InputMaybe<TextAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  location: TextAttributeInput;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name: TextAttributeInput;
  password?: InputMaybe<TextAttributeInput>;
  queries?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  ref?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  transformations?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  username?: InputMaybe<TextAttributeInput>;
};

/** A Git Repository integrated with Infrahub, Git-side will not be updated */
export type CoreReadOnlyRepositoryDelete = {
  __typename?: "CoreReadOnlyRepositoryDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A Git Repository integrated with Infrahub, Git-side will not be updated */
export type CoreReadOnlyRepositoryUpdate = {
  __typename?: "CoreReadOnlyRepositoryUpdate";
  object?: Maybe<CoreReadOnlyRepository>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreReadOnlyRepositoryUpdateInput = {
  checks?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  commit?: InputMaybe<TextAttributeInput>;
  description?: InputMaybe<TextAttributeInput>;
  id: Scalars["String"];
  location?: InputMaybe<TextAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name?: InputMaybe<TextAttributeInput>;
  password?: InputMaybe<TextAttributeInput>;
  queries?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  ref?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  transformations?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  username?: InputMaybe<TextAttributeInput>;
};

/** A Git Repository integrated with Infrahub, Git-side will not be updated */
export type CoreReadOnlyRepositoryUpsert = {
  __typename?: "CoreReadOnlyRepositoryUpsert";
  object?: Maybe<CoreReadOnlyRepository>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A Git Repository integrated with Infrahub */
export type CoreRepository = CoreGenericRepository &
  CoreNode &
  CoreTaskTarget &
  LineageOwner &
  LineageSource & {
    __typename?: "CoreRepository";
    _updated_at?: Maybe<Scalars["DateTime"]>;
    checks?: Maybe<NestedPaginatedCoreCheckDefinition>;
    commit?: Maybe<TextAttribute>;
    default_branch?: Maybe<TextAttribute>;
    description?: Maybe<TextAttribute>;
    display_label?: Maybe<Scalars["String"]>;
    id: Scalars["String"];
    location: TextAttribute;
    member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    name: TextAttribute;
    password?: Maybe<TextAttribute>;
    queries?: Maybe<NestedPaginatedCoreGraphQlQuery>;
    subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    tags?: Maybe<NestedPaginatedBuiltinTag>;
    transformations?: Maybe<NestedPaginatedCoreTransformation>;
    username?: Maybe<TextAttribute>;
  };

/** A Git Repository integrated with Infrahub */
export type CoreRepositoryChecksArgs = {
  class_name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  class_name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  class_name__owner__id?: InputMaybe<Scalars["ID"]>;
  class_name__source__id?: InputMaybe<Scalars["ID"]>;
  class_name__value?: InputMaybe<Scalars["String"]>;
  class_name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  file_path__is_protected?: InputMaybe<Scalars["Boolean"]>;
  file_path__is_visible?: InputMaybe<Scalars["Boolean"]>;
  file_path__owner__id?: InputMaybe<Scalars["ID"]>;
  file_path__source__id?: InputMaybe<Scalars["ID"]>;
  file_path__value?: InputMaybe<Scalars["String"]>;
  file_path__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  parameters__is_protected?: InputMaybe<Scalars["Boolean"]>;
  parameters__is_visible?: InputMaybe<Scalars["Boolean"]>;
  parameters__owner__id?: InputMaybe<Scalars["ID"]>;
  parameters__source__id?: InputMaybe<Scalars["ID"]>;
  parameters__value?: InputMaybe<Scalars["GenericScalar"]>;
  parameters__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  timeout__is_protected?: InputMaybe<Scalars["Boolean"]>;
  timeout__is_visible?: InputMaybe<Scalars["Boolean"]>;
  timeout__owner__id?: InputMaybe<Scalars["ID"]>;
  timeout__source__id?: InputMaybe<Scalars["ID"]>;
  timeout__value?: InputMaybe<Scalars["Int"]>;
  timeout__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
};

/** A Git Repository integrated with Infrahub */
export type CoreRepositoryMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A Git Repository integrated with Infrahub */
export type CoreRepositoryQueriesArgs = {
  depth__is_protected?: InputMaybe<Scalars["Boolean"]>;
  depth__is_visible?: InputMaybe<Scalars["Boolean"]>;
  depth__owner__id?: InputMaybe<Scalars["ID"]>;
  depth__source__id?: InputMaybe<Scalars["ID"]>;
  depth__value?: InputMaybe<Scalars["Int"]>;
  depth__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  height__is_protected?: InputMaybe<Scalars["Boolean"]>;
  height__is_visible?: InputMaybe<Scalars["Boolean"]>;
  height__owner__id?: InputMaybe<Scalars["ID"]>;
  height__source__id?: InputMaybe<Scalars["ID"]>;
  height__value?: InputMaybe<Scalars["Int"]>;
  height__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  models__is_protected?: InputMaybe<Scalars["Boolean"]>;
  models__is_visible?: InputMaybe<Scalars["Boolean"]>;
  models__owner__id?: InputMaybe<Scalars["ID"]>;
  models__source__id?: InputMaybe<Scalars["ID"]>;
  models__value?: InputMaybe<Scalars["GenericScalar"]>;
  models__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  operations__is_protected?: InputMaybe<Scalars["Boolean"]>;
  operations__is_visible?: InputMaybe<Scalars["Boolean"]>;
  operations__owner__id?: InputMaybe<Scalars["ID"]>;
  operations__source__id?: InputMaybe<Scalars["ID"]>;
  operations__value?: InputMaybe<Scalars["GenericScalar"]>;
  operations__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  query__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__owner__id?: InputMaybe<Scalars["ID"]>;
  query__source__id?: InputMaybe<Scalars["ID"]>;
  query__value?: InputMaybe<Scalars["String"]>;
  query__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  variables__is_protected?: InputMaybe<Scalars["Boolean"]>;
  variables__is_visible?: InputMaybe<Scalars["Boolean"]>;
  variables__owner__id?: InputMaybe<Scalars["ID"]>;
  variables__source__id?: InputMaybe<Scalars["ID"]>;
  variables__value?: InputMaybe<Scalars["GenericScalar"]>;
  variables__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
};

/** A Git Repository integrated with Infrahub */
export type CoreRepositorySubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A Git Repository integrated with Infrahub */
export type CoreRepositoryTagsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A Git Repository integrated with Infrahub */
export type CoreRepositoryTransformationsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  timeout__is_protected?: InputMaybe<Scalars["Boolean"]>;
  timeout__is_visible?: InputMaybe<Scalars["Boolean"]>;
  timeout__owner__id?: InputMaybe<Scalars["ID"]>;
  timeout__source__id?: InputMaybe<Scalars["ID"]>;
  timeout__value?: InputMaybe<Scalars["Int"]>;
  timeout__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
};

/** A Git Repository integrated with Infrahub */
export type CoreRepositoryCreate = {
  __typename?: "CoreRepositoryCreate";
  object?: Maybe<CoreRepository>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreRepositoryCreateInput = {
  checks?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  commit?: InputMaybe<TextAttributeInput>;
  default_branch?: InputMaybe<TextAttributeInput>;
  description?: InputMaybe<TextAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  location: TextAttributeInput;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name: TextAttributeInput;
  password?: InputMaybe<TextAttributeInput>;
  queries?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  transformations?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  username?: InputMaybe<TextAttributeInput>;
};

/** A Git Repository integrated with Infrahub */
export type CoreRepositoryDelete = {
  __typename?: "CoreRepositoryDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A Git Repository integrated with Infrahub */
export type CoreRepositoryUpdate = {
  __typename?: "CoreRepositoryUpdate";
  object?: Maybe<CoreRepository>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreRepositoryUpdateInput = {
  checks?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  commit?: InputMaybe<TextAttributeInput>;
  default_branch?: InputMaybe<TextAttributeInput>;
  description?: InputMaybe<TextAttributeInput>;
  id: Scalars["String"];
  location?: InputMaybe<TextAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name?: InputMaybe<TextAttributeInput>;
  password?: InputMaybe<TextAttributeInput>;
  queries?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  transformations?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  username?: InputMaybe<TextAttributeInput>;
};

/** A Git Repository integrated with Infrahub */
export type CoreRepositoryUpsert = {
  __typename?: "CoreRepositoryUpsert";
  object?: Maybe<CoreRepository>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A Validator related to a specific repository */
export type CoreRepositoryValidator = CoreNode &
  CoreValidator & {
    __typename?: "CoreRepositoryValidator";
    _updated_at?: Maybe<Scalars["DateTime"]>;
    checks?: Maybe<NestedPaginatedCoreCheck>;
    completed_at?: Maybe<TextAttribute>;
    conclusion?: Maybe<TextAttribute>;
    display_label?: Maybe<Scalars["String"]>;
    id: Scalars["String"];
    label?: Maybe<TextAttribute>;
    member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    proposed_change?: Maybe<NestedEdgedCoreProposedChange>;
    repository?: Maybe<NestedEdgedCoreGenericRepository>;
    started_at?: Maybe<TextAttribute>;
    state?: Maybe<TextAttribute>;
    subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  };

/** A Validator related to a specific repository */
export type CoreRepositoryValidatorChecksArgs = {
  conclusion__is_protected?: InputMaybe<Scalars["Boolean"]>;
  conclusion__is_visible?: InputMaybe<Scalars["Boolean"]>;
  conclusion__owner__id?: InputMaybe<Scalars["ID"]>;
  conclusion__source__id?: InputMaybe<Scalars["ID"]>;
  conclusion__value?: InputMaybe<Scalars["String"]>;
  conclusion__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  created_at__source__id?: InputMaybe<Scalars["ID"]>;
  created_at__value?: InputMaybe<Scalars["String"]>;
  created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  kind__is_protected?: InputMaybe<Scalars["Boolean"]>;
  kind__is_visible?: InputMaybe<Scalars["Boolean"]>;
  kind__owner__id?: InputMaybe<Scalars["ID"]>;
  kind__source__id?: InputMaybe<Scalars["ID"]>;
  kind__value?: InputMaybe<Scalars["String"]>;
  kind__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  message__is_protected?: InputMaybe<Scalars["Boolean"]>;
  message__is_visible?: InputMaybe<Scalars["Boolean"]>;
  message__owner__id?: InputMaybe<Scalars["ID"]>;
  message__source__id?: InputMaybe<Scalars["ID"]>;
  message__value?: InputMaybe<Scalars["String"]>;
  message__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  origin__is_protected?: InputMaybe<Scalars["Boolean"]>;
  origin__is_visible?: InputMaybe<Scalars["Boolean"]>;
  origin__owner__id?: InputMaybe<Scalars["ID"]>;
  origin__source__id?: InputMaybe<Scalars["ID"]>;
  origin__value?: InputMaybe<Scalars["String"]>;
  origin__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  severity__is_protected?: InputMaybe<Scalars["Boolean"]>;
  severity__is_visible?: InputMaybe<Scalars["Boolean"]>;
  severity__owner__id?: InputMaybe<Scalars["ID"]>;
  severity__source__id?: InputMaybe<Scalars["ID"]>;
  severity__value?: InputMaybe<Scalars["String"]>;
  severity__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

/** A Validator related to a specific repository */
export type CoreRepositoryValidatorMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A Validator related to a specific repository */
export type CoreRepositoryValidatorSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A Validator related to a specific repository */
export type CoreRepositoryValidatorCreate = {
  __typename?: "CoreRepositoryValidatorCreate";
  object?: Maybe<CoreRepositoryValidator>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreRepositoryValidatorCreateInput = {
  checks?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  completed_at?: InputMaybe<TextAttributeInput>;
  conclusion?: InputMaybe<TextAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  label?: InputMaybe<TextAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  proposed_change: RelatedNodeInput;
  repository: RelatedNodeInput;
  started_at?: InputMaybe<TextAttributeInput>;
  state?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** A Validator related to a specific repository */
export type CoreRepositoryValidatorDelete = {
  __typename?: "CoreRepositoryValidatorDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A Validator related to a specific repository */
export type CoreRepositoryValidatorUpdate = {
  __typename?: "CoreRepositoryValidatorUpdate";
  object?: Maybe<CoreRepositoryValidator>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreRepositoryValidatorUpdateInput = {
  checks?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  completed_at?: InputMaybe<TextAttributeInput>;
  conclusion?: InputMaybe<TextAttributeInput>;
  id: Scalars["String"];
  label?: InputMaybe<TextAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  proposed_change?: InputMaybe<RelatedNodeInput>;
  repository?: InputMaybe<RelatedNodeInput>;
  started_at?: InputMaybe<TextAttributeInput>;
  state?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** A Validator related to a specific repository */
export type CoreRepositoryValidatorUpsert = {
  __typename?: "CoreRepositoryValidatorUpsert";
  object?: Maybe<CoreRepositoryValidator>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A check related to the schema */
export type CoreSchemaCheck = CoreCheck &
  CoreNode & {
    __typename?: "CoreSchemaCheck";
    _updated_at?: Maybe<Scalars["DateTime"]>;
    conclusion?: Maybe<TextAttribute>;
    conflicts: JsonAttribute;
    created_at?: Maybe<TextAttribute>;
    display_label?: Maybe<Scalars["String"]>;
    id: Scalars["String"];
    kind: TextAttribute;
    label?: Maybe<TextAttribute>;
    member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    message?: Maybe<TextAttribute>;
    name?: Maybe<TextAttribute>;
    origin: TextAttribute;
    severity?: Maybe<TextAttribute>;
    subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    validator?: Maybe<NestedEdgedCoreValidator>;
  };

/** A check related to the schema */
export type CoreSchemaCheckMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A check related to the schema */
export type CoreSchemaCheckSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A check related to the schema */
export type CoreSchemaCheckCreate = {
  __typename?: "CoreSchemaCheckCreate";
  object?: Maybe<CoreSchemaCheck>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreSchemaCheckCreateInput = {
  conclusion?: InputMaybe<TextAttributeInput>;
  conflicts: JsonAttributeInput;
  created_at?: InputMaybe<TextAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  kind: TextAttributeInput;
  label?: InputMaybe<TextAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  message?: InputMaybe<TextAttributeInput>;
  name?: InputMaybe<TextAttributeInput>;
  origin: TextAttributeInput;
  severity?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  validator: RelatedNodeInput;
};

/** A check related to the schema */
export type CoreSchemaCheckDelete = {
  __typename?: "CoreSchemaCheckDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A check related to the schema */
export type CoreSchemaCheckUpdate = {
  __typename?: "CoreSchemaCheckUpdate";
  object?: Maybe<CoreSchemaCheck>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreSchemaCheckUpdateInput = {
  conclusion?: InputMaybe<TextAttributeInput>;
  conflicts?: InputMaybe<JsonAttributeInput>;
  created_at?: InputMaybe<TextAttributeInput>;
  id: Scalars["String"];
  kind?: InputMaybe<TextAttributeInput>;
  label?: InputMaybe<TextAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  message?: InputMaybe<TextAttributeInput>;
  name?: InputMaybe<TextAttributeInput>;
  origin?: InputMaybe<TextAttributeInput>;
  severity?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  validator?: InputMaybe<RelatedNodeInput>;
};

/** A check related to the schema */
export type CoreSchemaCheckUpsert = {
  __typename?: "CoreSchemaCheckUpsert";
  object?: Maybe<CoreSchemaCheck>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A validator related to the schema */
export type CoreSchemaValidator = CoreNode &
  CoreValidator & {
    __typename?: "CoreSchemaValidator";
    _updated_at?: Maybe<Scalars["DateTime"]>;
    checks?: Maybe<NestedPaginatedCoreCheck>;
    completed_at?: Maybe<TextAttribute>;
    conclusion?: Maybe<TextAttribute>;
    display_label?: Maybe<Scalars["String"]>;
    id: Scalars["String"];
    label?: Maybe<TextAttribute>;
    member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    proposed_change?: Maybe<NestedEdgedCoreProposedChange>;
    started_at?: Maybe<TextAttribute>;
    state?: Maybe<TextAttribute>;
    subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  };

/** A validator related to the schema */
export type CoreSchemaValidatorChecksArgs = {
  conclusion__is_protected?: InputMaybe<Scalars["Boolean"]>;
  conclusion__is_visible?: InputMaybe<Scalars["Boolean"]>;
  conclusion__owner__id?: InputMaybe<Scalars["ID"]>;
  conclusion__source__id?: InputMaybe<Scalars["ID"]>;
  conclusion__value?: InputMaybe<Scalars["String"]>;
  conclusion__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  created_at__source__id?: InputMaybe<Scalars["ID"]>;
  created_at__value?: InputMaybe<Scalars["String"]>;
  created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  kind__is_protected?: InputMaybe<Scalars["Boolean"]>;
  kind__is_visible?: InputMaybe<Scalars["Boolean"]>;
  kind__owner__id?: InputMaybe<Scalars["ID"]>;
  kind__source__id?: InputMaybe<Scalars["ID"]>;
  kind__value?: InputMaybe<Scalars["String"]>;
  kind__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  message__is_protected?: InputMaybe<Scalars["Boolean"]>;
  message__is_visible?: InputMaybe<Scalars["Boolean"]>;
  message__owner__id?: InputMaybe<Scalars["ID"]>;
  message__source__id?: InputMaybe<Scalars["ID"]>;
  message__value?: InputMaybe<Scalars["String"]>;
  message__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  origin__is_protected?: InputMaybe<Scalars["Boolean"]>;
  origin__is_visible?: InputMaybe<Scalars["Boolean"]>;
  origin__owner__id?: InputMaybe<Scalars["ID"]>;
  origin__source__id?: InputMaybe<Scalars["ID"]>;
  origin__value?: InputMaybe<Scalars["String"]>;
  origin__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  severity__is_protected?: InputMaybe<Scalars["Boolean"]>;
  severity__is_visible?: InputMaybe<Scalars["Boolean"]>;
  severity__owner__id?: InputMaybe<Scalars["ID"]>;
  severity__source__id?: InputMaybe<Scalars["ID"]>;
  severity__value?: InputMaybe<Scalars["String"]>;
  severity__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

/** A validator related to the schema */
export type CoreSchemaValidatorMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A validator related to the schema */
export type CoreSchemaValidatorSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A validator related to the schema */
export type CoreSchemaValidatorCreate = {
  __typename?: "CoreSchemaValidatorCreate";
  object?: Maybe<CoreSchemaValidator>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreSchemaValidatorCreateInput = {
  checks?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  completed_at?: InputMaybe<TextAttributeInput>;
  conclusion?: InputMaybe<TextAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  label?: InputMaybe<TextAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  proposed_change: RelatedNodeInput;
  started_at?: InputMaybe<TextAttributeInput>;
  state?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** A validator related to the schema */
export type CoreSchemaValidatorDelete = {
  __typename?: "CoreSchemaValidatorDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A validator related to the schema */
export type CoreSchemaValidatorUpdate = {
  __typename?: "CoreSchemaValidatorUpdate";
  object?: Maybe<CoreSchemaValidator>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreSchemaValidatorUpdateInput = {
  checks?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  completed_at?: InputMaybe<TextAttributeInput>;
  conclusion?: InputMaybe<TextAttributeInput>;
  id: Scalars["String"];
  label?: InputMaybe<TextAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  proposed_change?: InputMaybe<RelatedNodeInput>;
  started_at?: InputMaybe<TextAttributeInput>;
  state?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** A validator related to the schema */
export type CoreSchemaValidatorUpsert = {
  __typename?: "CoreSchemaValidatorUpsert";
  object?: Maybe<CoreSchemaValidator>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A standard check */
export type CoreStandardCheck = CoreCheck &
  CoreNode & {
    __typename?: "CoreStandardCheck";
    _updated_at?: Maybe<Scalars["DateTime"]>;
    conclusion?: Maybe<TextAttribute>;
    created_at?: Maybe<TextAttribute>;
    display_label?: Maybe<Scalars["String"]>;
    id: Scalars["String"];
    kind: TextAttribute;
    label?: Maybe<TextAttribute>;
    member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    message?: Maybe<TextAttribute>;
    name?: Maybe<TextAttribute>;
    origin: TextAttribute;
    severity?: Maybe<TextAttribute>;
    subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    validator?: Maybe<NestedEdgedCoreValidator>;
  };

/** A standard check */
export type CoreStandardCheckMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A standard check */
export type CoreStandardCheckSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A standard check */
export type CoreStandardCheckCreate = {
  __typename?: "CoreStandardCheckCreate";
  object?: Maybe<CoreStandardCheck>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreStandardCheckCreateInput = {
  conclusion?: InputMaybe<TextAttributeInput>;
  created_at?: InputMaybe<TextAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  kind: TextAttributeInput;
  label?: InputMaybe<TextAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  message?: InputMaybe<TextAttributeInput>;
  name?: InputMaybe<TextAttributeInput>;
  origin: TextAttributeInput;
  severity?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  validator: RelatedNodeInput;
};

/** A standard check */
export type CoreStandardCheckDelete = {
  __typename?: "CoreStandardCheckDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A standard check */
export type CoreStandardCheckUpdate = {
  __typename?: "CoreStandardCheckUpdate";
  object?: Maybe<CoreStandardCheck>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreStandardCheckUpdateInput = {
  conclusion?: InputMaybe<TextAttributeInput>;
  created_at?: InputMaybe<TextAttributeInput>;
  id: Scalars["String"];
  kind?: InputMaybe<TextAttributeInput>;
  label?: InputMaybe<TextAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  message?: InputMaybe<TextAttributeInput>;
  name?: InputMaybe<TextAttributeInput>;
  origin?: InputMaybe<TextAttributeInput>;
  severity?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  validator?: InputMaybe<RelatedNodeInput>;
};

/** A standard check */
export type CoreStandardCheckUpsert = {
  __typename?: "CoreStandardCheckUpsert";
  object?: Maybe<CoreStandardCheck>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** Group of nodes of any kind. */
export type CoreStandardGroup = CoreGroup & {
  __typename?: "CoreStandardGroup";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  ancestors?: Maybe<NestedPaginatedCoreGroup>;
  children?: Maybe<NestedPaginatedCoreGroup>;
  descendants?: Maybe<NestedPaginatedCoreGroup>;
  description?: Maybe<TextAttribute>;
  display_label?: Maybe<Scalars["String"]>;
  id: Scalars["String"];
  label?: Maybe<TextAttribute>;
  members?: Maybe<NestedPaginatedCoreNode>;
  name: TextAttribute;
  parent?: Maybe<NestedEdgedCoreGroup>;
  subscribers?: Maybe<NestedPaginatedCoreNode>;
};

/** Group of nodes of any kind. */
export type CoreStandardGroupAncestorsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Group of nodes of any kind. */
export type CoreStandardGroupChildrenArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  include_descendants?: InputMaybe<Scalars["Boolean"]>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Group of nodes of any kind. */
export type CoreStandardGroupDescendantsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Group of nodes of any kind. */
export type CoreStandardGroupMembersArgs = {
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  include_descendants?: InputMaybe<Scalars["Boolean"]>;
  limit?: InputMaybe<Scalars["Int"]>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Group of nodes of any kind. */
export type CoreStandardGroupSubscribersArgs = {
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  include_descendants?: InputMaybe<Scalars["Boolean"]>;
  limit?: InputMaybe<Scalars["Int"]>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Group of nodes of any kind. */
export type CoreStandardGroupCreate = {
  __typename?: "CoreStandardGroupCreate";
  object?: Maybe<CoreStandardGroup>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreStandardGroupCreateInput = {
  children?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  description?: InputMaybe<TextAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  label?: InputMaybe<TextAttributeInput>;
  members?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name: TextAttributeInput;
  parent?: InputMaybe<RelatedNodeInput>;
  subscribers?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** Group of nodes of any kind. */
export type CoreStandardGroupDelete = {
  __typename?: "CoreStandardGroupDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** Group of nodes of any kind. */
export type CoreStandardGroupUpdate = {
  __typename?: "CoreStandardGroupUpdate";
  object?: Maybe<CoreStandardGroup>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreStandardGroupUpdateInput = {
  children?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  description?: InputMaybe<TextAttributeInput>;
  id: Scalars["String"];
  label?: InputMaybe<TextAttributeInput>;
  members?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name?: InputMaybe<TextAttributeInput>;
  parent?: InputMaybe<RelatedNodeInput>;
  subscribers?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** Group of nodes of any kind. */
export type CoreStandardGroupUpsert = {
  __typename?: "CoreStandardGroupUpsert";
  object?: Maybe<CoreStandardGroup>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A webhook that connects to an external integration */
export type CoreStandardWebhook = CoreNode &
  CoreTaskTarget &
  CoreWebhook & {
    __typename?: "CoreStandardWebhook";
    _updated_at?: Maybe<Scalars["DateTime"]>;
    description?: Maybe<TextAttribute>;
    display_label?: Maybe<Scalars["String"]>;
    id: Scalars["String"];
    member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    name: TextAttribute;
    shared_key: TextAttribute;
    subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    url: TextAttribute;
    validate_certificates?: Maybe<CheckboxAttribute>;
  };

/** A webhook that connects to an external integration */
export type CoreStandardWebhookMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A webhook that connects to an external integration */
export type CoreStandardWebhookSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A webhook that connects to an external integration */
export type CoreStandardWebhookCreate = {
  __typename?: "CoreStandardWebhookCreate";
  object?: Maybe<CoreStandardWebhook>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreStandardWebhookCreateInput = {
  description?: InputMaybe<TextAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name: TextAttributeInput;
  shared_key: TextAttributeInput;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  url: TextAttributeInput;
  validate_certificates?: InputMaybe<CheckboxAttributeInput>;
};

/** A webhook that connects to an external integration */
export type CoreStandardWebhookDelete = {
  __typename?: "CoreStandardWebhookDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A webhook that connects to an external integration */
export type CoreStandardWebhookUpdate = {
  __typename?: "CoreStandardWebhookUpdate";
  object?: Maybe<CoreStandardWebhook>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreStandardWebhookUpdateInput = {
  description?: InputMaybe<TextAttributeInput>;
  id: Scalars["String"];
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name?: InputMaybe<TextAttributeInput>;
  shared_key?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  url?: InputMaybe<TextAttributeInput>;
  validate_certificates?: InputMaybe<CheckboxAttributeInput>;
};

/** A webhook that connects to an external integration */
export type CoreStandardWebhookUpsert = {
  __typename?: "CoreStandardWebhookUpsert";
  object?: Maybe<CoreStandardWebhook>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** Extend a node to be associated with tasks */
export type CoreTaskTarget = {
  display_label?: Maybe<Scalars["String"]>;
  /** Unique identifier */
  id?: Maybe<Scalars["String"]>;
  member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
};

/** Extend a node to be associated with tasks */
export type CoreTaskTargetMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Extend a node to be associated with tasks */
export type CoreTaskTargetSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A thread on a Proposed Change */
export type CoreThread = {
  change?: Maybe<NestedEdgedCoreProposedChange>;
  comments?: Maybe<NestedPaginatedCoreThreadComment>;
  created_at?: Maybe<TextAttribute>;
  created_by?: Maybe<NestedEdgedCoreAccount>;
  display_label?: Maybe<Scalars["String"]>;
  /** Unique identifier */
  id?: Maybe<Scalars["String"]>;
  label?: Maybe<TextAttribute>;
  member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  resolved?: Maybe<CheckboxAttribute>;
  subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
};

/** A thread on a Proposed Change */
export type CoreThreadCommentsArgs = {
  created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  created_at__source__id?: InputMaybe<Scalars["ID"]>;
  created_at__value?: InputMaybe<Scalars["String"]>;
  created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  offset?: InputMaybe<Scalars["Int"]>;
  text__is_protected?: InputMaybe<Scalars["Boolean"]>;
  text__is_visible?: InputMaybe<Scalars["Boolean"]>;
  text__owner__id?: InputMaybe<Scalars["ID"]>;
  text__source__id?: InputMaybe<Scalars["ID"]>;
  text__value?: InputMaybe<Scalars["String"]>;
  text__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

/** A thread on a Proposed Change */
export type CoreThreadMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A thread on a Proposed Change */
export type CoreThreadSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A comment on thread within a Proposed Change */
export type CoreThreadComment = CoreComment &
  CoreNode & {
    __typename?: "CoreThreadComment";
    _updated_at?: Maybe<Scalars["DateTime"]>;
    created_at?: Maybe<TextAttribute>;
    created_by?: Maybe<NestedEdgedCoreAccount>;
    display_label?: Maybe<Scalars["String"]>;
    id: Scalars["String"];
    member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    text: TextAttribute;
    thread?: Maybe<NestedEdgedCoreThread>;
  };

/** A comment on thread within a Proposed Change */
export type CoreThreadCommentMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A comment on thread within a Proposed Change */
export type CoreThreadCommentSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A comment on thread within a Proposed Change */
export type CoreThreadCommentCreate = {
  __typename?: "CoreThreadCommentCreate";
  object?: Maybe<CoreThreadComment>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreThreadCommentCreateInput = {
  created_at?: InputMaybe<TextAttributeInput>;
  created_by?: InputMaybe<RelatedNodeInput>;
  id?: InputMaybe<Scalars["String"]>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  text: TextAttributeInput;
  thread: RelatedNodeInput;
};

/** A comment on thread within a Proposed Change */
export type CoreThreadCommentDelete = {
  __typename?: "CoreThreadCommentDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A comment on thread within a Proposed Change */
export type CoreThreadCommentUpdate = {
  __typename?: "CoreThreadCommentUpdate";
  object?: Maybe<CoreThreadComment>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreThreadCommentUpdateInput = {
  created_at?: InputMaybe<TextAttributeInput>;
  created_by?: InputMaybe<RelatedNodeInput>;
  id: Scalars["String"];
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  text?: InputMaybe<TextAttributeInput>;
  thread?: InputMaybe<RelatedNodeInput>;
};

/** A comment on thread within a Proposed Change */
export type CoreThreadCommentUpsert = {
  __typename?: "CoreThreadCommentUpsert";
  object?: Maybe<CoreThreadComment>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A file rendered from a Jinja2 template */
export type CoreTransformJinja2 = CoreNode &
  CoreTransformation & {
    __typename?: "CoreTransformJinja2";
    _updated_at?: Maybe<Scalars["DateTime"]>;
    description?: Maybe<TextAttribute>;
    display_label?: Maybe<Scalars["String"]>;
    id: Scalars["String"];
    label?: Maybe<TextAttribute>;
    member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    name: TextAttribute;
    query?: Maybe<NestedEdgedCoreGraphQlQuery>;
    repository?: Maybe<NestedEdgedCoreGenericRepository>;
    subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    tags?: Maybe<NestedPaginatedBuiltinTag>;
    template_path: TextAttribute;
    timeout?: Maybe<NumberAttribute>;
  };

/** A file rendered from a Jinja2 template */
export type CoreTransformJinja2Member_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A file rendered from a Jinja2 template */
export type CoreTransformJinja2Subscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A file rendered from a Jinja2 template */
export type CoreTransformJinja2TagsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A file rendered from a Jinja2 template */
export type CoreTransformJinja2Create = {
  __typename?: "CoreTransformJinja2Create";
  object?: Maybe<CoreTransformJinja2>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreTransformJinja2CreateInput = {
  description?: InputMaybe<TextAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  label?: InputMaybe<TextAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name: TextAttributeInput;
  query: RelatedNodeInput;
  repository: RelatedNodeInput;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  template_path: TextAttributeInput;
  timeout?: InputMaybe<NumberAttributeInput>;
};

/** A file rendered from a Jinja2 template */
export type CoreTransformJinja2Delete = {
  __typename?: "CoreTransformJinja2Delete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A file rendered from a Jinja2 template */
export type CoreTransformJinja2Update = {
  __typename?: "CoreTransformJinja2Update";
  object?: Maybe<CoreTransformJinja2>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreTransformJinja2UpdateInput = {
  description?: InputMaybe<TextAttributeInput>;
  id: Scalars["String"];
  label?: InputMaybe<TextAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name?: InputMaybe<TextAttributeInput>;
  query?: InputMaybe<RelatedNodeInput>;
  repository?: InputMaybe<RelatedNodeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  template_path?: InputMaybe<TextAttributeInput>;
  timeout?: InputMaybe<NumberAttributeInput>;
};

/** A file rendered from a Jinja2 template */
export type CoreTransformJinja2Upsert = {
  __typename?: "CoreTransformJinja2Upsert";
  object?: Maybe<CoreTransformJinja2>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A transform function written in Python */
export type CoreTransformPython = CoreNode &
  CoreTransformation & {
    __typename?: "CoreTransformPython";
    _updated_at?: Maybe<Scalars["DateTime"]>;
    class_name: TextAttribute;
    description?: Maybe<TextAttribute>;
    display_label?: Maybe<Scalars["String"]>;
    file_path: TextAttribute;
    id: Scalars["String"];
    label?: Maybe<TextAttribute>;
    member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    name: TextAttribute;
    query?: Maybe<NestedEdgedCoreGraphQlQuery>;
    repository?: Maybe<NestedEdgedCoreGenericRepository>;
    subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    tags?: Maybe<NestedPaginatedBuiltinTag>;
    timeout?: Maybe<NumberAttribute>;
  };

/** A transform function written in Python */
export type CoreTransformPythonMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A transform function written in Python */
export type CoreTransformPythonSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A transform function written in Python */
export type CoreTransformPythonTagsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A transform function written in Python */
export type CoreTransformPythonCreate = {
  __typename?: "CoreTransformPythonCreate";
  object?: Maybe<CoreTransformPython>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreTransformPythonCreateInput = {
  class_name: TextAttributeInput;
  description?: InputMaybe<TextAttributeInput>;
  file_path: TextAttributeInput;
  id?: InputMaybe<Scalars["String"]>;
  label?: InputMaybe<TextAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name: TextAttributeInput;
  query: RelatedNodeInput;
  repository: RelatedNodeInput;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  timeout?: InputMaybe<NumberAttributeInput>;
};

/** A transform function written in Python */
export type CoreTransformPythonDelete = {
  __typename?: "CoreTransformPythonDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A transform function written in Python */
export type CoreTransformPythonUpdate = {
  __typename?: "CoreTransformPythonUpdate";
  object?: Maybe<CoreTransformPython>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreTransformPythonUpdateInput = {
  class_name?: InputMaybe<TextAttributeInput>;
  description?: InputMaybe<TextAttributeInput>;
  file_path?: InputMaybe<TextAttributeInput>;
  id: Scalars["String"];
  label?: InputMaybe<TextAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name?: InputMaybe<TextAttributeInput>;
  query?: InputMaybe<RelatedNodeInput>;
  repository?: InputMaybe<RelatedNodeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  timeout?: InputMaybe<NumberAttributeInput>;
};

/** A transform function written in Python */
export type CoreTransformPythonUpsert = {
  __typename?: "CoreTransformPythonUpsert";
  object?: Maybe<CoreTransformPython>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** Generic Transformation Object. */
export type CoreTransformation = {
  description?: Maybe<TextAttribute>;
  display_label?: Maybe<Scalars["String"]>;
  /** Unique identifier */
  id?: Maybe<Scalars["String"]>;
  label?: Maybe<TextAttribute>;
  member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  name: TextAttribute;
  query?: Maybe<NestedEdgedCoreGraphQlQuery>;
  repository?: Maybe<NestedEdgedCoreGenericRepository>;
  subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  tags?: Maybe<NestedPaginatedBuiltinTag>;
  timeout?: Maybe<NumberAttribute>;
};

/** Generic Transformation Object. */
export type CoreTransformationMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Generic Transformation Object. */
export type CoreTransformationSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Generic Transformation Object. */
export type CoreTransformationTagsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A Validator related to a user defined checks in a repository */
export type CoreUserValidator = CoreNode &
  CoreValidator & {
    __typename?: "CoreUserValidator";
    _updated_at?: Maybe<Scalars["DateTime"]>;
    check_definition?: Maybe<NestedEdgedCoreCheckDefinition>;
    checks?: Maybe<NestedPaginatedCoreCheck>;
    completed_at?: Maybe<TextAttribute>;
    conclusion?: Maybe<TextAttribute>;
    display_label?: Maybe<Scalars["String"]>;
    id: Scalars["String"];
    label?: Maybe<TextAttribute>;
    member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    proposed_change?: Maybe<NestedEdgedCoreProposedChange>;
    repository?: Maybe<NestedEdgedCoreGenericRepository>;
    started_at?: Maybe<TextAttribute>;
    state?: Maybe<TextAttribute>;
    subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  };

/** A Validator related to a user defined checks in a repository */
export type CoreUserValidatorChecksArgs = {
  conclusion__is_protected?: InputMaybe<Scalars["Boolean"]>;
  conclusion__is_visible?: InputMaybe<Scalars["Boolean"]>;
  conclusion__owner__id?: InputMaybe<Scalars["ID"]>;
  conclusion__source__id?: InputMaybe<Scalars["ID"]>;
  conclusion__value?: InputMaybe<Scalars["String"]>;
  conclusion__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  created_at__source__id?: InputMaybe<Scalars["ID"]>;
  created_at__value?: InputMaybe<Scalars["String"]>;
  created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  kind__is_protected?: InputMaybe<Scalars["Boolean"]>;
  kind__is_visible?: InputMaybe<Scalars["Boolean"]>;
  kind__owner__id?: InputMaybe<Scalars["ID"]>;
  kind__source__id?: InputMaybe<Scalars["ID"]>;
  kind__value?: InputMaybe<Scalars["String"]>;
  kind__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  message__is_protected?: InputMaybe<Scalars["Boolean"]>;
  message__is_visible?: InputMaybe<Scalars["Boolean"]>;
  message__owner__id?: InputMaybe<Scalars["ID"]>;
  message__source__id?: InputMaybe<Scalars["ID"]>;
  message__value?: InputMaybe<Scalars["String"]>;
  message__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  origin__is_protected?: InputMaybe<Scalars["Boolean"]>;
  origin__is_visible?: InputMaybe<Scalars["Boolean"]>;
  origin__owner__id?: InputMaybe<Scalars["ID"]>;
  origin__source__id?: InputMaybe<Scalars["ID"]>;
  origin__value?: InputMaybe<Scalars["String"]>;
  origin__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  severity__is_protected?: InputMaybe<Scalars["Boolean"]>;
  severity__is_visible?: InputMaybe<Scalars["Boolean"]>;
  severity__owner__id?: InputMaybe<Scalars["ID"]>;
  severity__source__id?: InputMaybe<Scalars["ID"]>;
  severity__value?: InputMaybe<Scalars["String"]>;
  severity__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

/** A Validator related to a user defined checks in a repository */
export type CoreUserValidatorMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A Validator related to a user defined checks in a repository */
export type CoreUserValidatorSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A Validator related to a user defined checks in a repository */
export type CoreUserValidatorCreate = {
  __typename?: "CoreUserValidatorCreate";
  object?: Maybe<CoreUserValidator>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreUserValidatorCreateInput = {
  check_definition: RelatedNodeInput;
  checks?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  completed_at?: InputMaybe<TextAttributeInput>;
  conclusion?: InputMaybe<TextAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  label?: InputMaybe<TextAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  proposed_change: RelatedNodeInput;
  repository: RelatedNodeInput;
  started_at?: InputMaybe<TextAttributeInput>;
  state?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** A Validator related to a user defined checks in a repository */
export type CoreUserValidatorDelete = {
  __typename?: "CoreUserValidatorDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A Validator related to a user defined checks in a repository */
export type CoreUserValidatorUpdate = {
  __typename?: "CoreUserValidatorUpdate";
  object?: Maybe<CoreUserValidator>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreUserValidatorUpdateInput = {
  check_definition?: InputMaybe<RelatedNodeInput>;
  checks?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  completed_at?: InputMaybe<TextAttributeInput>;
  conclusion?: InputMaybe<TextAttributeInput>;
  id: Scalars["String"];
  label?: InputMaybe<TextAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  proposed_change?: InputMaybe<RelatedNodeInput>;
  repository?: InputMaybe<RelatedNodeInput>;
  started_at?: InputMaybe<TextAttributeInput>;
  state?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** A Validator related to a user defined checks in a repository */
export type CoreUserValidatorUpsert = {
  __typename?: "CoreUserValidatorUpsert";
  object?: Maybe<CoreUserValidator>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type CoreValidator = {
  checks?: Maybe<NestedPaginatedCoreCheck>;
  completed_at?: Maybe<TextAttribute>;
  conclusion?: Maybe<TextAttribute>;
  display_label?: Maybe<Scalars["String"]>;
  /** Unique identifier */
  id?: Maybe<Scalars["String"]>;
  label?: Maybe<TextAttribute>;
  member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  proposed_change?: Maybe<NestedEdgedCoreProposedChange>;
  started_at?: Maybe<TextAttribute>;
  state?: Maybe<TextAttribute>;
  subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
};

export type CoreValidatorChecksArgs = {
  conclusion__is_protected?: InputMaybe<Scalars["Boolean"]>;
  conclusion__is_visible?: InputMaybe<Scalars["Boolean"]>;
  conclusion__owner__id?: InputMaybe<Scalars["ID"]>;
  conclusion__source__id?: InputMaybe<Scalars["ID"]>;
  conclusion__value?: InputMaybe<Scalars["String"]>;
  conclusion__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  created_at__source__id?: InputMaybe<Scalars["ID"]>;
  created_at__value?: InputMaybe<Scalars["String"]>;
  created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  kind__is_protected?: InputMaybe<Scalars["Boolean"]>;
  kind__is_visible?: InputMaybe<Scalars["Boolean"]>;
  kind__owner__id?: InputMaybe<Scalars["ID"]>;
  kind__source__id?: InputMaybe<Scalars["ID"]>;
  kind__value?: InputMaybe<Scalars["String"]>;
  kind__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  message__is_protected?: InputMaybe<Scalars["Boolean"]>;
  message__is_visible?: InputMaybe<Scalars["Boolean"]>;
  message__owner__id?: InputMaybe<Scalars["ID"]>;
  message__source__id?: InputMaybe<Scalars["ID"]>;
  message__value?: InputMaybe<Scalars["String"]>;
  message__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  origin__is_protected?: InputMaybe<Scalars["Boolean"]>;
  origin__is_visible?: InputMaybe<Scalars["Boolean"]>;
  origin__owner__id?: InputMaybe<Scalars["ID"]>;
  origin__source__id?: InputMaybe<Scalars["ID"]>;
  origin__value?: InputMaybe<Scalars["String"]>;
  origin__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  severity__is_protected?: InputMaybe<Scalars["Boolean"]>;
  severity__is_visible?: InputMaybe<Scalars["Boolean"]>;
  severity__owner__id?: InputMaybe<Scalars["ID"]>;
  severity__source__id?: InputMaybe<Scalars["ID"]>;
  severity__value?: InputMaybe<Scalars["String"]>;
  severity__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type CoreValidatorMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

export type CoreValidatorSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A webhook that connects to an external integration */
export type CoreWebhook = {
  description?: Maybe<TextAttribute>;
  display_label?: Maybe<Scalars["String"]>;
  /** Unique identifier */
  id?: Maybe<Scalars["String"]>;
  member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  name: TextAttribute;
  subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  url: TextAttribute;
  validate_certificates?: Maybe<CheckboxAttribute>;
};

/** A webhook that connects to an external integration */
export type CoreWebhookMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A webhook that connects to an external integration */
export type CoreWebhookSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

export type DeleteInput = {
  id: Scalars["String"];
};

/** . */
export type DemoEdgeFabric = CoreNode & {
  __typename?: "DemoEdgeFabric";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  description?: Maybe<TextAttribute>;
  display_label?: Maybe<Scalars["String"]>;
  id: Scalars["String"];
  member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  name: TextAttribute;
  nbr_racks: NumberAttribute;
  subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  tags?: Maybe<NestedPaginatedBuiltinTag>;
};

/** . */
export type DemoEdgeFabricMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** . */
export type DemoEdgeFabricSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** . */
export type DemoEdgeFabricTagsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** . */
export type DemoEdgeFabricCreate = {
  __typename?: "DemoEdgeFabricCreate";
  object?: Maybe<DemoEdgeFabric>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type DemoEdgeFabricCreateInput = {
  description?: InputMaybe<TextAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name: TextAttributeInput;
  nbr_racks: NumberAttributeInput;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** . */
export type DemoEdgeFabricDelete = {
  __typename?: "DemoEdgeFabricDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** . */
export type DemoEdgeFabricUpdate = {
  __typename?: "DemoEdgeFabricUpdate";
  object?: Maybe<DemoEdgeFabric>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type DemoEdgeFabricUpdateInput = {
  description?: InputMaybe<TextAttributeInput>;
  id: Scalars["String"];
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name?: InputMaybe<TextAttributeInput>;
  nbr_racks?: InputMaybe<NumberAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** . */
export type DemoEdgeFabricUpsert = {
  __typename?: "DemoEdgeFabricUpsert";
  object?: Maybe<DemoEdgeFabric>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** An enumeration. */
export enum DiffAction {
  Added = "ADDED",
  Removed = "REMOVED",
  Unchanged = "UNCHANGED",
  Updated = "UPDATED",
}

export type DiffActionSummary = {
  __typename?: "DiffActionSummary";
  action: DiffAction;
  summary?: Maybe<DiffSummaryCount>;
};

/** An enumeration. */
export enum DiffElementType {
  Attribute = "ATTRIBUTE",
  RelationshipMany = "RELATIONSHIP_MANY",
  RelationshipOne = "RELATIONSHIP_ONE",
}

export type DiffSummaryCount = {
  __typename?: "DiffSummaryCount";
  added?: Maybe<Scalars["Int"]>;
  removed?: Maybe<Scalars["Int"]>;
  updated?: Maybe<Scalars["Int"]>;
};

export type DiffSummaryElementAttribute = DiffSummaryElementInterface & {
  __typename?: "DiffSummaryElementAttribute";
  action: DiffAction;
  element_type: DiffElementType;
  name: Scalars["String"];
  summary: DiffSummaryCount;
};

export type DiffSummaryElementInterface = {
  action: DiffAction;
  element_type: DiffElementType;
  name: Scalars["String"];
  summary: DiffSummaryCount;
};

export type DiffSummaryElementRelationshipMany = DiffSummaryElementInterface & {
  __typename?: "DiffSummaryElementRelationshipMany";
  action: DiffAction;
  element_type: DiffElementType;
  name: Scalars["String"];
  peers?: Maybe<Array<Maybe<DiffActionSummary>>>;
  summary: DiffSummaryCount;
};

export type DiffSummaryElementRelationshipOne = DiffSummaryElementInterface & {
  __typename?: "DiffSummaryElementRelationshipOne";
  action: DiffAction;
  element_type: DiffElementType;
  name: Scalars["String"];
  summary: DiffSummaryCount;
};

export type DiffSummaryEntry = {
  __typename?: "DiffSummaryEntry";
  action?: Maybe<DiffAction>;
  branch: Scalars["String"];
  display_label?: Maybe<Scalars["String"]>;
  elements?: Maybe<Array<Maybe<DiffSummaryElementInterface>>>;
  id: Scalars["String"];
  kind: Scalars["String"];
};

export type DiffSummaryEntryOld = {
  __typename?: "DiffSummaryEntryOld";
  actions: Array<Maybe<Scalars["String"]>>;
  branch: Scalars["String"];
  kind: Scalars["String"];
  node: Scalars["String"];
};

/** Attribute of type Dropdown */
export type Dropdown = AttributeInterface & {
  __typename?: "Dropdown";
  color?: Maybe<Scalars["String"]>;
  description?: Maybe<Scalars["String"]>;
  id?: Maybe<Scalars["String"]>;
  is_inherited?: Maybe<Scalars["Boolean"]>;
  is_protected?: Maybe<Scalars["Boolean"]>;
  is_visible?: Maybe<Scalars["Boolean"]>;
  label?: Maybe<Scalars["String"]>;
  owner?: Maybe<LineageOwner>;
  source?: Maybe<LineageSource>;
  updated_at?: Maybe<Scalars["DateTime"]>;
  value?: Maybe<Scalars["String"]>;
};

export type DropdownFields = {
  __typename?: "DropdownFields";
  color?: Maybe<Scalars["String"]>;
  description?: Maybe<Scalars["String"]>;
  label?: Maybe<Scalars["String"]>;
  value?: Maybe<Scalars["String"]>;
};

/** Represents the role of an object */
export type EdgedBuiltinRole = {
  __typename?: "EdgedBuiltinRole";
  node?: Maybe<BuiltinRole>;
};

/** Status represents the current state of an object: active, maintenance */
export type EdgedBuiltinStatus = {
  __typename?: "EdgedBuiltinStatus";
  node?: Maybe<BuiltinStatus>;
};

/** Standard Tag object to attached to other objects to provide some context. */
export type EdgedBuiltinTag = {
  __typename?: "EdgedBuiltinTag";
  node?: Maybe<BuiltinTag>;
};

/** User Account for Infrahub */
export type EdgedCoreAccount = {
  __typename?: "EdgedCoreAccount";
  node?: Maybe<CoreAccount>;
};

export type EdgedCoreArtifact = {
  __typename?: "EdgedCoreArtifact";
  node?: Maybe<CoreArtifact>;
};

/** A check related to an artifact */
export type EdgedCoreArtifactCheck = {
  __typename?: "EdgedCoreArtifactCheck";
  node?: Maybe<CoreArtifactCheck>;
};

export type EdgedCoreArtifactDefinition = {
  __typename?: "EdgedCoreArtifactDefinition";
  node?: Maybe<CoreArtifactDefinition>;
};

/** Extend a node to be associated with artifacts */
export type EdgedCoreArtifactTarget = {
  __typename?: "EdgedCoreArtifactTarget";
  node?: Maybe<CoreArtifactTarget>;
};

/** A thread related to an artifact on a proposed change */
export type EdgedCoreArtifactThread = {
  __typename?: "EdgedCoreArtifactThread";
  node?: Maybe<CoreArtifactThread>;
};

/** A validator related to the artifacts */
export type EdgedCoreArtifactValidator = {
  __typename?: "EdgedCoreArtifactValidator";
  node?: Maybe<CoreArtifactValidator>;
};

/** A comment on proposed change */
export type EdgedCoreChangeComment = {
  __typename?: "EdgedCoreChangeComment";
  node?: Maybe<CoreChangeComment>;
};

/** A thread on proposed change */
export type EdgedCoreChangeThread = {
  __typename?: "EdgedCoreChangeThread";
  node?: Maybe<CoreChangeThread>;
};

export type EdgedCoreCheck = {
  __typename?: "EdgedCoreCheck";
  node?: Maybe<CoreCheck>;
};

export type EdgedCoreCheckDefinition = {
  __typename?: "EdgedCoreCheckDefinition";
  node?: Maybe<CoreCheckDefinition>;
};

/** A comment on a Proposed Change */
export type EdgedCoreComment = {
  __typename?: "EdgedCoreComment";
  node?: Maybe<CoreComment>;
};

/** A webhook that connects to an external integration */
export type EdgedCoreCustomWebhook = {
  __typename?: "EdgedCoreCustomWebhook";
  node?: Maybe<CoreCustomWebhook>;
};

/** A check related to some Data */
export type EdgedCoreDataCheck = {
  __typename?: "EdgedCoreDataCheck";
  node?: Maybe<CoreDataCheck>;
};

/** A check to validate the data integrity between two branches */
export type EdgedCoreDataValidator = {
  __typename?: "EdgedCoreDataValidator";
  node?: Maybe<CoreDataValidator>;
};

/** A check related to a file in a Git Repository */
export type EdgedCoreFileCheck = {
  __typename?: "EdgedCoreFileCheck";
  node?: Maybe<CoreFileCheck>;
};

/** A thread related to a file on a proposed change */
export type EdgedCoreFileThread = {
  __typename?: "EdgedCoreFileThread";
  node?: Maybe<CoreFileThread>;
};

/** A Git Repository integrated with Infrahub */
export type EdgedCoreGenericRepository = {
  __typename?: "EdgedCoreGenericRepository";
  node?: Maybe<CoreGenericRepository>;
};

/** A pre-defined GraphQL Query */
export type EdgedCoreGraphQlQuery = {
  __typename?: "EdgedCoreGraphQLQuery";
  node?: Maybe<CoreGraphQlQuery>;
};

/** Group of nodes associated with a given GraphQLQuery. */
export type EdgedCoreGraphQlQueryGroup = {
  __typename?: "EdgedCoreGraphQLQueryGroup";
  node?: Maybe<CoreGraphQlQueryGroup>;
};

/** Generic Group Object. */
export type EdgedCoreGroup = {
  __typename?: "EdgedCoreGroup";
  node?: Maybe<CoreGroup>;
};

/** Base Node in Infrahub. */
export type EdgedCoreNode = {
  __typename?: "EdgedCoreNode";
  node?: Maybe<CoreNode>;
};

/** A thread related to an object on a proposed change */
export type EdgedCoreObjectThread = {
  __typename?: "EdgedCoreObjectThread";
  node?: Maybe<CoreObjectThread>;
};

/** An organization represent a legal entity, a company */
export type EdgedCoreOrganization = {
  __typename?: "EdgedCoreOrganization";
  node?: Maybe<CoreOrganization>;
};

/** Metadata related to a proposed change */
export type EdgedCoreProposedChange = {
  __typename?: "EdgedCoreProposedChange";
  node?: Maybe<CoreProposedChange>;
};

/** A Git Repository integrated with Infrahub, Git-side will not be updated */
export type EdgedCoreReadOnlyRepository = {
  __typename?: "EdgedCoreReadOnlyRepository";
  node?: Maybe<CoreReadOnlyRepository>;
};

/** A Git Repository integrated with Infrahub */
export type EdgedCoreRepository = {
  __typename?: "EdgedCoreRepository";
  node?: Maybe<CoreRepository>;
};

/** A Validator related to a specific repository */
export type EdgedCoreRepositoryValidator = {
  __typename?: "EdgedCoreRepositoryValidator";
  node?: Maybe<CoreRepositoryValidator>;
};

/** A check related to the schema */
export type EdgedCoreSchemaCheck = {
  __typename?: "EdgedCoreSchemaCheck";
  node?: Maybe<CoreSchemaCheck>;
};

/** A validator related to the schema */
export type EdgedCoreSchemaValidator = {
  __typename?: "EdgedCoreSchemaValidator";
  node?: Maybe<CoreSchemaValidator>;
};

/** A standard check */
export type EdgedCoreStandardCheck = {
  __typename?: "EdgedCoreStandardCheck";
  node?: Maybe<CoreStandardCheck>;
};

/** Group of nodes of any kind. */
export type EdgedCoreStandardGroup = {
  __typename?: "EdgedCoreStandardGroup";
  node?: Maybe<CoreStandardGroup>;
};

/** A webhook that connects to an external integration */
export type EdgedCoreStandardWebhook = {
  __typename?: "EdgedCoreStandardWebhook";
  node?: Maybe<CoreStandardWebhook>;
};

/** Extend a node to be associated with tasks */
export type EdgedCoreTaskTarget = {
  __typename?: "EdgedCoreTaskTarget";
  node?: Maybe<CoreTaskTarget>;
};

/** A thread on a Proposed Change */
export type EdgedCoreThread = {
  __typename?: "EdgedCoreThread";
  node?: Maybe<CoreThread>;
};

/** A comment on thread within a Proposed Change */
export type EdgedCoreThreadComment = {
  __typename?: "EdgedCoreThreadComment";
  node?: Maybe<CoreThreadComment>;
};

/** A file rendered from a Jinja2 template */
export type EdgedCoreTransformJinja2 = {
  __typename?: "EdgedCoreTransformJinja2";
  node?: Maybe<CoreTransformJinja2>;
};

/** A transform function written in Python */
export type EdgedCoreTransformPython = {
  __typename?: "EdgedCoreTransformPython";
  node?: Maybe<CoreTransformPython>;
};

/** Generic Transformation Object. */
export type EdgedCoreTransformation = {
  __typename?: "EdgedCoreTransformation";
  node?: Maybe<CoreTransformation>;
};

/** A Validator related to a user defined checks in a repository */
export type EdgedCoreUserValidator = {
  __typename?: "EdgedCoreUserValidator";
  node?: Maybe<CoreUserValidator>;
};

export type EdgedCoreValidator = {
  __typename?: "EdgedCoreValidator";
  node?: Maybe<CoreValidator>;
};

/** A webhook that connects to an external integration */
export type EdgedCoreWebhook = {
  __typename?: "EdgedCoreWebhook";
  node?: Maybe<CoreWebhook>;
};

/** . */
export type EdgedDemoEdgeFabric = {
  __typename?: "EdgedDemoEdgeFabric";
  node?: Maybe<DemoEdgeFabric>;
};

/** An Autonomous System (AS) is a set of Internet routable IP prefixes belonging to a network */
export type EdgedInfraAutonomousSystem = {
  __typename?: "EdgedInfraAutonomousSystem";
  node?: Maybe<InfraAutonomousSystem>;
};

/** A BGP Peer Group is used to regroup parameters that are shared across multiple peers */
export type EdgedInfraBgpPeerGroup = {
  __typename?: "EdgedInfraBGPPeerGroup";
  node?: Maybe<InfraBgpPeerGroup>;
};

/** A BGP Session represent a point to point connection between two routers */
export type EdgedInfraBgpSession = {
  __typename?: "EdgedInfraBGPSession";
  node?: Maybe<InfraBgpSession>;
};

/** A Circuit represent a single physical link between two locations */
export type EdgedInfraCircuit = {
  __typename?: "EdgedInfraCircuit";
  node?: Maybe<InfraCircuit>;
};

/** A Circuit endpoint is attached to each end of a circuit */
export type EdgedInfraCircuitEndpoint = {
  __typename?: "EdgedInfraCircuitEndpoint";
  node?: Maybe<InfraCircuitEndpoint>;
};

/** A continent on planet earth. */
export type EdgedInfraContinent = {
  __typename?: "EdgedInfraContinent";
  node?: Maybe<InfraContinent>;
};

/** A country within a continent. */
export type EdgedInfraCountry = {
  __typename?: "EdgedInfraCountry";
  node?: Maybe<InfraCountry>;
};

/** Generic Device object */
export type EdgedInfraDevice = {
  __typename?: "EdgedInfraDevice";
  node?: Maybe<InfraDevice>;
};

/** Generic Endpoint to connect two objects together */
export type EdgedInfraEndpoint = {
  __typename?: "EdgedInfraEndpoint";
  node?: Maybe<InfraEndpoint>;
};

/** IP Address */
export type EdgedInfraIpAddress = {
  __typename?: "EdgedInfraIPAddress";
  node?: Maybe<InfraIpAddress>;
};

/** Generic Network Interface */
export type EdgedInfraInterface = {
  __typename?: "EdgedInfraInterface";
  node?: Maybe<InfraInterface>;
};

/** Network Layer 2 Interface */
export type EdgedInfraInterfaceL2 = {
  __typename?: "EdgedInfraInterfaceL2";
  node?: Maybe<InfraInterfaceL2>;
};

/** Network Layer 3 Interface */
export type EdgedInfraInterfaceL3 = {
  __typename?: "EdgedInfraInterfaceL3";
  node?: Maybe<InfraInterfaceL3>;
};

/** Generic hierarchical location */
export type EdgedInfraLocation = {
  __typename?: "EdgedInfraLocation";
  node?: Maybe<InfraLocation>;
};

/** A Platform represents the type of software running on a device */
export type EdgedInfraPlatform = {
  __typename?: "EdgedInfraPlatform";
  node?: Maybe<InfraPlatform>;
};

/** A site within a country. */
export type EdgedInfraSite = {
  __typename?: "EdgedInfraSite";
  node?: Maybe<InfraSite>;
};

/** A VLAN is a logical grouping of devices in the same broadcast domain */
export type EdgedInfraVlan = {
  __typename?: "EdgedInfraVLAN";
  node?: Maybe<InfraVlan>;
};

/** Token for User Account */
export type EdgedInternalAccountToken = {
  __typename?: "EdgedInternalAccountToken";
  node?: Maybe<InternalAccountToken>;
};

/** Refresh Token */
export type EdgedInternalRefreshToken = {
  __typename?: "EdgedInternalRefreshToken";
  node?: Maybe<InternalRefreshToken>;
};

/** Any Entities that is responsible for some data. */
export type EdgedLineageOwner = {
  __typename?: "EdgedLineageOwner";
  node?: Maybe<LineageOwner>;
};

/** Any Entities that stores or produces data. */
export type EdgedLineageSource = {
  __typename?: "EdgedLineageSource";
  node?: Maybe<LineageSource>;
};

/** object with all attributes */
export type EdgedTestAllinone = {
  __typename?: "EdgedTestAllinone";
  node?: Maybe<TestAllinone>;
};

/** Attribute of type Text */
export type IpHost = AttributeInterface & {
  __typename?: "IPHost";
  hostmask?: Maybe<Scalars["String"]>;
  id?: Maybe<Scalars["String"]>;
  ip?: Maybe<Scalars["String"]>;
  is_inherited?: Maybe<Scalars["Boolean"]>;
  is_protected?: Maybe<Scalars["Boolean"]>;
  is_visible?: Maybe<Scalars["Boolean"]>;
  netmask?: Maybe<Scalars["String"]>;
  owner?: Maybe<LineageOwner>;
  prefixlen?: Maybe<Scalars["String"]>;
  source?: Maybe<LineageSource>;
  updated_at?: Maybe<Scalars["DateTime"]>;
  value?: Maybe<Scalars["String"]>;
  version?: Maybe<Scalars["Int"]>;
  with_hostmask?: Maybe<Scalars["String"]>;
  with_netmask?: Maybe<Scalars["String"]>;
};

/** Attribute of type Text */
export type IpNetwork = AttributeInterface & {
  __typename?: "IPNetwork";
  broadcast_address?: Maybe<Scalars["String"]>;
  hostmask?: Maybe<Scalars["String"]>;
  id?: Maybe<Scalars["String"]>;
  is_inherited?: Maybe<Scalars["Boolean"]>;
  is_protected?: Maybe<Scalars["Boolean"]>;
  is_visible?: Maybe<Scalars["Boolean"]>;
  netmask?: Maybe<Scalars["String"]>;
  num_addresses?: Maybe<Scalars["Int"]>;
  owner?: Maybe<LineageOwner>;
  prefixlen?: Maybe<Scalars["String"]>;
  source?: Maybe<LineageSource>;
  updated_at?: Maybe<Scalars["DateTime"]>;
  value?: Maybe<Scalars["String"]>;
  version?: Maybe<Scalars["Int"]>;
  with_hostmask?: Maybe<Scalars["String"]>;
  with_netmask?: Maybe<Scalars["String"]>;
};

export type Info = {
  __typename?: "Info";
  deployment_id: Scalars["String"];
  version: Scalars["String"];
};

/** An Autonomous System (AS) is a set of Internet routable IP prefixes belonging to a network */
export type InfraAutonomousSystem = CoreNode & {
  __typename?: "InfraAutonomousSystem";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  asn: NumberAttribute;
  description?: Maybe<TextAttribute>;
  display_label?: Maybe<Scalars["String"]>;
  id: Scalars["String"];
  member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  name: TextAttribute;
  organization?: Maybe<NestedEdgedCoreOrganization>;
  subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
};

/** An Autonomous System (AS) is a set of Internet routable IP prefixes belonging to a network */
export type InfraAutonomousSystemMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** An Autonomous System (AS) is a set of Internet routable IP prefixes belonging to a network */
export type InfraAutonomousSystemSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** An Autonomous System (AS) is a set of Internet routable IP prefixes belonging to a network */
export type InfraAutonomousSystemCreate = {
  __typename?: "InfraAutonomousSystemCreate";
  object?: Maybe<InfraAutonomousSystem>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type InfraAutonomousSystemCreateInput = {
  asn: NumberAttributeInput;
  description?: InputMaybe<TextAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name: TextAttributeInput;
  organization: RelatedNodeInput;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** An Autonomous System (AS) is a set of Internet routable IP prefixes belonging to a network */
export type InfraAutonomousSystemDelete = {
  __typename?: "InfraAutonomousSystemDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** An Autonomous System (AS) is a set of Internet routable IP prefixes belonging to a network */
export type InfraAutonomousSystemUpdate = {
  __typename?: "InfraAutonomousSystemUpdate";
  object?: Maybe<InfraAutonomousSystem>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type InfraAutonomousSystemUpdateInput = {
  asn?: InputMaybe<NumberAttributeInput>;
  description?: InputMaybe<TextAttributeInput>;
  id: Scalars["String"];
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name?: InputMaybe<TextAttributeInput>;
  organization?: InputMaybe<RelatedNodeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** An Autonomous System (AS) is a set of Internet routable IP prefixes belonging to a network */
export type InfraAutonomousSystemUpsert = {
  __typename?: "InfraAutonomousSystemUpsert";
  object?: Maybe<InfraAutonomousSystem>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A BGP Peer Group is used to regroup parameters that are shared across multiple peers */
export type InfraBgpPeerGroup = CoreNode & {
  __typename?: "InfraBGPPeerGroup";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  description?: Maybe<TextAttribute>;
  display_label?: Maybe<Scalars["String"]>;
  export_policies?: Maybe<TextAttribute>;
  id: Scalars["String"];
  import_policies?: Maybe<TextAttribute>;
  local_as?: Maybe<NestedEdgedInfraAutonomousSystem>;
  member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  name: TextAttribute;
  remote_as?: Maybe<NestedEdgedInfraAutonomousSystem>;
  subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
};

/** A BGP Peer Group is used to regroup parameters that are shared across multiple peers */
export type InfraBgpPeerGroupMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A BGP Peer Group is used to regroup parameters that are shared across multiple peers */
export type InfraBgpPeerGroupSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A BGP Peer Group is used to regroup parameters that are shared across multiple peers */
export type InfraBgpPeerGroupCreate = {
  __typename?: "InfraBGPPeerGroupCreate";
  object?: Maybe<InfraBgpPeerGroup>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type InfraBgpPeerGroupCreateInput = {
  description?: InputMaybe<TextAttributeInput>;
  export_policies?: InputMaybe<TextAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  import_policies?: InputMaybe<TextAttributeInput>;
  local_as?: InputMaybe<RelatedNodeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name: TextAttributeInput;
  remote_as?: InputMaybe<RelatedNodeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** A BGP Peer Group is used to regroup parameters that are shared across multiple peers */
export type InfraBgpPeerGroupDelete = {
  __typename?: "InfraBGPPeerGroupDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A BGP Peer Group is used to regroup parameters that are shared across multiple peers */
export type InfraBgpPeerGroupUpdate = {
  __typename?: "InfraBGPPeerGroupUpdate";
  object?: Maybe<InfraBgpPeerGroup>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type InfraBgpPeerGroupUpdateInput = {
  description?: InputMaybe<TextAttributeInput>;
  export_policies?: InputMaybe<TextAttributeInput>;
  id: Scalars["String"];
  import_policies?: InputMaybe<TextAttributeInput>;
  local_as?: InputMaybe<RelatedNodeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name?: InputMaybe<TextAttributeInput>;
  remote_as?: InputMaybe<RelatedNodeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** A BGP Peer Group is used to regroup parameters that are shared across multiple peers */
export type InfraBgpPeerGroupUpsert = {
  __typename?: "InfraBGPPeerGroupUpsert";
  object?: Maybe<InfraBgpPeerGroup>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A BGP Session represent a point to point connection between two routers */
export type InfraBgpSession = CoreArtifactTarget &
  CoreNode & {
    __typename?: "InfraBGPSession";
    _updated_at?: Maybe<Scalars["DateTime"]>;
    artifacts?: Maybe<NestedPaginatedCoreArtifact>;
    description?: Maybe<TextAttribute>;
    device?: Maybe<NestedEdgedInfraDevice>;
    display_label?: Maybe<Scalars["String"]>;
    export_policies?: Maybe<TextAttribute>;
    id: Scalars["String"];
    import_policies?: Maybe<TextAttribute>;
    local_as?: Maybe<NestedEdgedInfraAutonomousSystem>;
    local_ip?: Maybe<NestedEdgedInfraIpAddress>;
    member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    peer_group?: Maybe<NestedEdgedInfraBgpPeerGroup>;
    peer_session?: Maybe<NestedEdgedInfraBgpSession>;
    remote_as?: Maybe<NestedEdgedInfraAutonomousSystem>;
    remote_ip?: Maybe<NestedEdgedInfraIpAddress>;
    role: Dropdown;
    status: Dropdown;
    subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    type: TextAttribute;
  };

/** A BGP Session represent a point to point connection between two routers */
export type InfraBgpSessionArtifactsArgs = {
  checksum__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checksum__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checksum__owner__id?: InputMaybe<Scalars["ID"]>;
  checksum__source__id?: InputMaybe<Scalars["ID"]>;
  checksum__value?: InputMaybe<Scalars["String"]>;
  checksum__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  content_type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  content_type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  content_type__owner__id?: InputMaybe<Scalars["ID"]>;
  content_type__source__id?: InputMaybe<Scalars["ID"]>;
  content_type__value?: InputMaybe<Scalars["String"]>;
  content_type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  parameters__is_protected?: InputMaybe<Scalars["Boolean"]>;
  parameters__is_visible?: InputMaybe<Scalars["Boolean"]>;
  parameters__owner__id?: InputMaybe<Scalars["ID"]>;
  parameters__source__id?: InputMaybe<Scalars["ID"]>;
  parameters__value?: InputMaybe<Scalars["GenericScalar"]>;
  parameters__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  status__is_protected?: InputMaybe<Scalars["Boolean"]>;
  status__is_visible?: InputMaybe<Scalars["Boolean"]>;
  status__owner__id?: InputMaybe<Scalars["ID"]>;
  status__source__id?: InputMaybe<Scalars["ID"]>;
  status__value?: InputMaybe<Scalars["String"]>;
  status__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  storage_id__is_protected?: InputMaybe<Scalars["Boolean"]>;
  storage_id__is_visible?: InputMaybe<Scalars["Boolean"]>;
  storage_id__owner__id?: InputMaybe<Scalars["ID"]>;
  storage_id__source__id?: InputMaybe<Scalars["ID"]>;
  storage_id__value?: InputMaybe<Scalars["String"]>;
  storage_id__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

/** A BGP Session represent a point to point connection between two routers */
export type InfraBgpSessionMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A BGP Session represent a point to point connection between two routers */
export type InfraBgpSessionSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A BGP Session represent a point to point connection between two routers */
export type InfraBgpSessionCreate = {
  __typename?: "InfraBGPSessionCreate";
  object?: Maybe<InfraBgpSession>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type InfraBgpSessionCreateInput = {
  artifacts?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  description?: InputMaybe<TextAttributeInput>;
  device?: InputMaybe<RelatedNodeInput>;
  export_policies?: InputMaybe<TextAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  import_policies?: InputMaybe<TextAttributeInput>;
  local_as?: InputMaybe<RelatedNodeInput>;
  local_ip?: InputMaybe<RelatedNodeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  peer_group?: InputMaybe<RelatedNodeInput>;
  peer_session?: InputMaybe<RelatedNodeInput>;
  remote_as?: InputMaybe<RelatedNodeInput>;
  remote_ip?: InputMaybe<RelatedNodeInput>;
  role: TextAttributeInput;
  status: TextAttributeInput;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  type: TextAttributeInput;
};

/** A BGP Session represent a point to point connection between two routers */
export type InfraBgpSessionDelete = {
  __typename?: "InfraBGPSessionDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A BGP Session represent a point to point connection between two routers */
export type InfraBgpSessionUpdate = {
  __typename?: "InfraBGPSessionUpdate";
  object?: Maybe<InfraBgpSession>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type InfraBgpSessionUpdateInput = {
  artifacts?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  description?: InputMaybe<TextAttributeInput>;
  device?: InputMaybe<RelatedNodeInput>;
  export_policies?: InputMaybe<TextAttributeInput>;
  id: Scalars["String"];
  import_policies?: InputMaybe<TextAttributeInput>;
  local_as?: InputMaybe<RelatedNodeInput>;
  local_ip?: InputMaybe<RelatedNodeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  peer_group?: InputMaybe<RelatedNodeInput>;
  peer_session?: InputMaybe<RelatedNodeInput>;
  remote_as?: InputMaybe<RelatedNodeInput>;
  remote_ip?: InputMaybe<RelatedNodeInput>;
  role?: InputMaybe<TextAttributeInput>;
  status?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  type?: InputMaybe<TextAttributeInput>;
};

/** A BGP Session represent a point to point connection between two routers */
export type InfraBgpSessionUpsert = {
  __typename?: "InfraBGPSessionUpsert";
  object?: Maybe<InfraBgpSession>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A Circuit represent a single physical link between two locations */
export type InfraCircuit = CoreNode & {
  __typename?: "InfraCircuit";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  circuit_id: TextAttribute;
  description?: Maybe<TextAttribute>;
  display_label?: Maybe<Scalars["String"]>;
  endpoints?: Maybe<NestedPaginatedInfraCircuitEndpoint>;
  id: Scalars["String"];
  member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  provider?: Maybe<NestedEdgedCoreOrganization>;
  role: Dropdown;
  status: Dropdown;
  subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  vendor_id?: Maybe<TextAttribute>;
};

/** A Circuit represent a single physical link between two locations */
export type InfraCircuitEndpointsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A Circuit represent a single physical link between two locations */
export type InfraCircuitMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A Circuit represent a single physical link between two locations */
export type InfraCircuitSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A Circuit represent a single physical link between two locations */
export type InfraCircuitCreate = {
  __typename?: "InfraCircuitCreate";
  object?: Maybe<InfraCircuit>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type InfraCircuitCreateInput = {
  circuit_id: TextAttributeInput;
  description?: InputMaybe<TextAttributeInput>;
  endpoints?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  id?: InputMaybe<Scalars["String"]>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  provider: RelatedNodeInput;
  role: TextAttributeInput;
  status: TextAttributeInput;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  vendor_id?: InputMaybe<TextAttributeInput>;
};

/** A Circuit represent a single physical link between two locations */
export type InfraCircuitDelete = {
  __typename?: "InfraCircuitDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A Circuit endpoint is attached to each end of a circuit */
export type InfraCircuitEndpoint = CoreNode &
  InfraEndpoint & {
    __typename?: "InfraCircuitEndpoint";
    _updated_at?: Maybe<Scalars["DateTime"]>;
    circuit?: Maybe<NestedEdgedInfraCircuit>;
    connected_endpoint?: Maybe<NestedEdgedInfraEndpoint>;
    description?: Maybe<TextAttribute>;
    display_label?: Maybe<Scalars["String"]>;
    id: Scalars["String"];
    member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    site?: Maybe<NestedEdgedInfraSite>;
    subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  };

/** A Circuit endpoint is attached to each end of a circuit */
export type InfraCircuitEndpointMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A Circuit endpoint is attached to each end of a circuit */
export type InfraCircuitEndpointSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A Circuit endpoint is attached to each end of a circuit */
export type InfraCircuitEndpointCreate = {
  __typename?: "InfraCircuitEndpointCreate";
  object?: Maybe<InfraCircuitEndpoint>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type InfraCircuitEndpointCreateInput = {
  circuit: RelatedNodeInput;
  connected_endpoint?: InputMaybe<RelatedNodeInput>;
  description?: InputMaybe<TextAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  site: RelatedNodeInput;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** A Circuit endpoint is attached to each end of a circuit */
export type InfraCircuitEndpointDelete = {
  __typename?: "InfraCircuitEndpointDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A Circuit endpoint is attached to each end of a circuit */
export type InfraCircuitEndpointUpdate = {
  __typename?: "InfraCircuitEndpointUpdate";
  object?: Maybe<InfraCircuitEndpoint>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type InfraCircuitEndpointUpdateInput = {
  circuit?: InputMaybe<RelatedNodeInput>;
  connected_endpoint?: InputMaybe<RelatedNodeInput>;
  description?: InputMaybe<TextAttributeInput>;
  id: Scalars["String"];
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  site?: InputMaybe<RelatedNodeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** A Circuit endpoint is attached to each end of a circuit */
export type InfraCircuitEndpointUpsert = {
  __typename?: "InfraCircuitEndpointUpsert";
  object?: Maybe<InfraCircuitEndpoint>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A Circuit represent a single physical link between two locations */
export type InfraCircuitUpdate = {
  __typename?: "InfraCircuitUpdate";
  object?: Maybe<InfraCircuit>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type InfraCircuitUpdateInput = {
  circuit_id?: InputMaybe<TextAttributeInput>;
  description?: InputMaybe<TextAttributeInput>;
  endpoints?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  id: Scalars["String"];
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  provider?: InputMaybe<RelatedNodeInput>;
  role?: InputMaybe<TextAttributeInput>;
  status?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  vendor_id?: InputMaybe<TextAttributeInput>;
};

/** A Circuit represent a single physical link between two locations */
export type InfraCircuitUpsert = {
  __typename?: "InfraCircuitUpsert";
  object?: Maybe<InfraCircuit>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A continent on planet earth. */
export type InfraContinent = CoreNode &
  InfraLocation & {
    __typename?: "InfraContinent";
    _updated_at?: Maybe<Scalars["DateTime"]>;
    ancestors?: Maybe<NestedPaginatedInfraLocation>;
    children?: Maybe<NestedPaginatedInfraCountry>;
    descendants?: Maybe<NestedPaginatedInfraLocation>;
    description?: Maybe<TextAttribute>;
    display_label?: Maybe<Scalars["String"]>;
    id: Scalars["String"];
    member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    name: TextAttribute;
    subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  };

/** A continent on planet earth. */
export type InfraContinentAncestorsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A continent on planet earth. */
export type InfraContinentChildrenArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  include_descendants?: InputMaybe<Scalars["Boolean"]>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A continent on planet earth. */
export type InfraContinentDescendantsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A continent on planet earth. */
export type InfraContinentMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  include_descendants?: InputMaybe<Scalars["Boolean"]>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A continent on planet earth. */
export type InfraContinentSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  include_descendants?: InputMaybe<Scalars["Boolean"]>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A continent on planet earth. */
export type InfraContinentCreate = {
  __typename?: "InfraContinentCreate";
  object?: Maybe<InfraContinent>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type InfraContinentCreateInput = {
  children?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  description?: InputMaybe<TextAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name: TextAttributeInput;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** A continent on planet earth. */
export type InfraContinentDelete = {
  __typename?: "InfraContinentDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A continent on planet earth. */
export type InfraContinentUpdate = {
  __typename?: "InfraContinentUpdate";
  object?: Maybe<InfraContinent>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type InfraContinentUpdateInput = {
  children?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  description?: InputMaybe<TextAttributeInput>;
  id: Scalars["String"];
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** A continent on planet earth. */
export type InfraContinentUpsert = {
  __typename?: "InfraContinentUpsert";
  object?: Maybe<InfraContinent>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A country within a continent. */
export type InfraCountry = CoreNode &
  InfraLocation & {
    __typename?: "InfraCountry";
    _updated_at?: Maybe<Scalars["DateTime"]>;
    ancestors?: Maybe<NestedPaginatedInfraLocation>;
    children?: Maybe<NestedPaginatedInfraSite>;
    descendants?: Maybe<NestedPaginatedInfraLocation>;
    description?: Maybe<TextAttribute>;
    display_label?: Maybe<Scalars["String"]>;
    id: Scalars["String"];
    member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    name: TextAttribute;
    parent?: Maybe<NestedEdgedInfraContinent>;
    subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  };

/** A country within a continent. */
export type InfraCountryAncestorsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A country within a continent. */
export type InfraCountryChildrenArgs = {
  address__is_protected?: InputMaybe<Scalars["Boolean"]>;
  address__is_visible?: InputMaybe<Scalars["Boolean"]>;
  address__owner__id?: InputMaybe<Scalars["ID"]>;
  address__source__id?: InputMaybe<Scalars["ID"]>;
  address__value?: InputMaybe<Scalars["String"]>;
  address__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  city__is_protected?: InputMaybe<Scalars["Boolean"]>;
  city__is_visible?: InputMaybe<Scalars["Boolean"]>;
  city__owner__id?: InputMaybe<Scalars["ID"]>;
  city__source__id?: InputMaybe<Scalars["ID"]>;
  city__value?: InputMaybe<Scalars["String"]>;
  city__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  contact__is_protected?: InputMaybe<Scalars["Boolean"]>;
  contact__is_visible?: InputMaybe<Scalars["Boolean"]>;
  contact__owner__id?: InputMaybe<Scalars["ID"]>;
  contact__source__id?: InputMaybe<Scalars["ID"]>;
  contact__value?: InputMaybe<Scalars["String"]>;
  contact__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  include_descendants?: InputMaybe<Scalars["Boolean"]>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A country within a continent. */
export type InfraCountryDescendantsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A country within a continent. */
export type InfraCountryMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  include_descendants?: InputMaybe<Scalars["Boolean"]>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A country within a continent. */
export type InfraCountrySubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  include_descendants?: InputMaybe<Scalars["Boolean"]>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A country within a continent. */
export type InfraCountryCreate = {
  __typename?: "InfraCountryCreate";
  object?: Maybe<InfraCountry>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type InfraCountryCreateInput = {
  children?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  description?: InputMaybe<TextAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name: TextAttributeInput;
  parent?: InputMaybe<RelatedNodeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** A country within a continent. */
export type InfraCountryDelete = {
  __typename?: "InfraCountryDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A country within a continent. */
export type InfraCountryUpdate = {
  __typename?: "InfraCountryUpdate";
  object?: Maybe<InfraCountry>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type InfraCountryUpdateInput = {
  children?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  description?: InputMaybe<TextAttributeInput>;
  id: Scalars["String"];
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name?: InputMaybe<TextAttributeInput>;
  parent?: InputMaybe<RelatedNodeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** A country within a continent. */
export type InfraCountryUpsert = {
  __typename?: "InfraCountryUpsert";
  object?: Maybe<InfraCountry>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** Generic Device object */
export type InfraDevice = CoreArtifactTarget &
  CoreNode & {
    __typename?: "InfraDevice";
    _updated_at?: Maybe<Scalars["DateTime"]>;
    artifacts?: Maybe<NestedPaginatedCoreArtifact>;
    asn?: Maybe<NestedEdgedInfraAutonomousSystem>;
    description?: Maybe<TextAttribute>;
    display_label?: Maybe<Scalars["String"]>;
    id: Scalars["String"];
    interfaces?: Maybe<NestedPaginatedInfraInterface>;
    member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    name: TextAttribute;
    platform?: Maybe<NestedEdgedInfraPlatform>;
    primary_address?: Maybe<NestedEdgedInfraIpAddress>;
    role?: Maybe<Dropdown>;
    site?: Maybe<NestedEdgedInfraSite>;
    status?: Maybe<Dropdown>;
    subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    tags?: Maybe<NestedPaginatedBuiltinTag>;
    type: TextAttribute;
  };

/** Generic Device object */
export type InfraDeviceArtifactsArgs = {
  checksum__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checksum__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checksum__owner__id?: InputMaybe<Scalars["ID"]>;
  checksum__source__id?: InputMaybe<Scalars["ID"]>;
  checksum__value?: InputMaybe<Scalars["String"]>;
  checksum__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  content_type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  content_type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  content_type__owner__id?: InputMaybe<Scalars["ID"]>;
  content_type__source__id?: InputMaybe<Scalars["ID"]>;
  content_type__value?: InputMaybe<Scalars["String"]>;
  content_type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  parameters__is_protected?: InputMaybe<Scalars["Boolean"]>;
  parameters__is_visible?: InputMaybe<Scalars["Boolean"]>;
  parameters__owner__id?: InputMaybe<Scalars["ID"]>;
  parameters__source__id?: InputMaybe<Scalars["ID"]>;
  parameters__value?: InputMaybe<Scalars["GenericScalar"]>;
  parameters__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  status__is_protected?: InputMaybe<Scalars["Boolean"]>;
  status__is_visible?: InputMaybe<Scalars["Boolean"]>;
  status__owner__id?: InputMaybe<Scalars["ID"]>;
  status__source__id?: InputMaybe<Scalars["ID"]>;
  status__value?: InputMaybe<Scalars["String"]>;
  status__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  storage_id__is_protected?: InputMaybe<Scalars["Boolean"]>;
  storage_id__is_visible?: InputMaybe<Scalars["Boolean"]>;
  storage_id__owner__id?: InputMaybe<Scalars["ID"]>;
  storage_id__source__id?: InputMaybe<Scalars["ID"]>;
  storage_id__value?: InputMaybe<Scalars["String"]>;
  storage_id__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

/** Generic Device object */
export type InfraDeviceInterfacesArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  enabled__is_protected?: InputMaybe<Scalars["Boolean"]>;
  enabled__is_visible?: InputMaybe<Scalars["Boolean"]>;
  enabled__owner__id?: InputMaybe<Scalars["ID"]>;
  enabled__source__id?: InputMaybe<Scalars["ID"]>;
  enabled__value?: InputMaybe<Scalars["Boolean"]>;
  enabled__values?: InputMaybe<Array<InputMaybe<Scalars["Boolean"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  mtu__is_protected?: InputMaybe<Scalars["Boolean"]>;
  mtu__is_visible?: InputMaybe<Scalars["Boolean"]>;
  mtu__owner__id?: InputMaybe<Scalars["ID"]>;
  mtu__source__id?: InputMaybe<Scalars["ID"]>;
  mtu__value?: InputMaybe<Scalars["Int"]>;
  mtu__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  role__owner__id?: InputMaybe<Scalars["ID"]>;
  role__source__id?: InputMaybe<Scalars["ID"]>;
  role__value?: InputMaybe<Scalars["String"]>;
  role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  speed__is_protected?: InputMaybe<Scalars["Boolean"]>;
  speed__is_visible?: InputMaybe<Scalars["Boolean"]>;
  speed__owner__id?: InputMaybe<Scalars["ID"]>;
  speed__source__id?: InputMaybe<Scalars["ID"]>;
  speed__value?: InputMaybe<Scalars["Int"]>;
  speed__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  status__is_protected?: InputMaybe<Scalars["Boolean"]>;
  status__is_visible?: InputMaybe<Scalars["Boolean"]>;
  status__owner__id?: InputMaybe<Scalars["ID"]>;
  status__source__id?: InputMaybe<Scalars["ID"]>;
  status__value?: InputMaybe<Scalars["String"]>;
  status__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

/** Generic Device object */
export type InfraDeviceMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Generic Device object */
export type InfraDeviceSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Generic Device object */
export type InfraDeviceTagsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Generic Device object */
export type InfraDeviceCreate = {
  __typename?: "InfraDeviceCreate";
  object?: Maybe<InfraDevice>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type InfraDeviceCreateInput = {
  artifacts?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  asn?: InputMaybe<RelatedNodeInput>;
  description?: InputMaybe<TextAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  interfaces?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name: TextAttributeInput;
  platform?: InputMaybe<RelatedNodeInput>;
  primary_address?: InputMaybe<RelatedNodeInput>;
  role?: InputMaybe<TextAttributeInput>;
  site: RelatedNodeInput;
  status?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  type: TextAttributeInput;
};

/** Generic Device object */
export type InfraDeviceDelete = {
  __typename?: "InfraDeviceDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** Generic Device object */
export type InfraDeviceUpdate = {
  __typename?: "InfraDeviceUpdate";
  object?: Maybe<InfraDevice>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type InfraDeviceUpdateInput = {
  artifacts?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  asn?: InputMaybe<RelatedNodeInput>;
  description?: InputMaybe<TextAttributeInput>;
  id: Scalars["String"];
  interfaces?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name?: InputMaybe<TextAttributeInput>;
  platform?: InputMaybe<RelatedNodeInput>;
  primary_address?: InputMaybe<RelatedNodeInput>;
  role?: InputMaybe<TextAttributeInput>;
  site?: InputMaybe<RelatedNodeInput>;
  status?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  type?: InputMaybe<TextAttributeInput>;
};

/** Generic Device object */
export type InfraDeviceUpsert = {
  __typename?: "InfraDeviceUpsert";
  object?: Maybe<InfraDevice>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** Generic Endpoint to connect two objects together */
export type InfraEndpoint = {
  connected_endpoint?: Maybe<NestedEdgedInfraEndpoint>;
  display_label?: Maybe<Scalars["String"]>;
  /** Unique identifier */
  id?: Maybe<Scalars["String"]>;
  member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
};

/** Generic Endpoint to connect two objects together */
export type InfraEndpointMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Generic Endpoint to connect two objects together */
export type InfraEndpointSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** IP Address */
export type InfraIpAddress = CoreNode & {
  __typename?: "InfraIPAddress";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  address: IpHost;
  description?: Maybe<TextAttribute>;
  display_label?: Maybe<Scalars["String"]>;
  id: Scalars["String"];
  interface?: Maybe<NestedEdgedInfraInterfaceL3>;
  member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
};

/** IP Address */
export type InfraIpAddressMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** IP Address */
export type InfraIpAddressSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** IP Address */
export type InfraIpAddressCreate = {
  __typename?: "InfraIPAddressCreate";
  object?: Maybe<InfraIpAddress>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type InfraIpAddressCreateInput = {
  address: TextAttributeInput;
  description?: InputMaybe<TextAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  interface?: InputMaybe<RelatedNodeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** IP Address */
export type InfraIpAddressDelete = {
  __typename?: "InfraIPAddressDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** IP Address */
export type InfraIpAddressUpdate = {
  __typename?: "InfraIPAddressUpdate";
  object?: Maybe<InfraIpAddress>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type InfraIpAddressUpdateInput = {
  address?: InputMaybe<TextAttributeInput>;
  description?: InputMaybe<TextAttributeInput>;
  id: Scalars["String"];
  interface?: InputMaybe<RelatedNodeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** IP Address */
export type InfraIpAddressUpsert = {
  __typename?: "InfraIPAddressUpsert";
  object?: Maybe<InfraIpAddress>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** Generic Network Interface */
export type InfraInterface = {
  description?: Maybe<TextAttribute>;
  device?: Maybe<NestedEdgedInfraDevice>;
  display_label?: Maybe<Scalars["String"]>;
  enabled?: Maybe<CheckboxAttribute>;
  /** Unique identifier */
  id?: Maybe<Scalars["String"]>;
  member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  mtu?: Maybe<NumberAttribute>;
  name: TextAttribute;
  role?: Maybe<Dropdown>;
  speed: NumberAttribute;
  status?: Maybe<Dropdown>;
  subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  tags?: Maybe<NestedPaginatedBuiltinTag>;
};

/** Generic Network Interface */
export type InfraInterfaceMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Generic Network Interface */
export type InfraInterfaceSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Generic Network Interface */
export type InfraInterfaceTagsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Network Layer 2 Interface */
export type InfraInterfaceL2 = CoreArtifactTarget &
  CoreNode &
  InfraEndpoint &
  InfraInterface & {
    __typename?: "InfraInterfaceL2";
    _updated_at?: Maybe<Scalars["DateTime"]>;
    artifacts?: Maybe<NestedPaginatedCoreArtifact>;
    connected_endpoint?: Maybe<NestedEdgedInfraEndpoint>;
    description?: Maybe<TextAttribute>;
    device?: Maybe<NestedEdgedInfraDevice>;
    display_label?: Maybe<Scalars["String"]>;
    enabled?: Maybe<CheckboxAttribute>;
    id: Scalars["String"];
    l2_mode: TextAttribute;
    member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    mtu?: Maybe<NumberAttribute>;
    name: TextAttribute;
    role?: Maybe<Dropdown>;
    speed: NumberAttribute;
    status?: Maybe<Dropdown>;
    subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    tagged_vlan?: Maybe<NestedPaginatedInfraVlan>;
    tags?: Maybe<NestedPaginatedBuiltinTag>;
    untagged_vlan?: Maybe<NestedEdgedInfraVlan>;
  };

/** Network Layer 2 Interface */
export type InfraInterfaceL2ArtifactsArgs = {
  checksum__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checksum__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checksum__owner__id?: InputMaybe<Scalars["ID"]>;
  checksum__source__id?: InputMaybe<Scalars["ID"]>;
  checksum__value?: InputMaybe<Scalars["String"]>;
  checksum__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  content_type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  content_type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  content_type__owner__id?: InputMaybe<Scalars["ID"]>;
  content_type__source__id?: InputMaybe<Scalars["ID"]>;
  content_type__value?: InputMaybe<Scalars["String"]>;
  content_type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  parameters__is_protected?: InputMaybe<Scalars["Boolean"]>;
  parameters__is_visible?: InputMaybe<Scalars["Boolean"]>;
  parameters__owner__id?: InputMaybe<Scalars["ID"]>;
  parameters__source__id?: InputMaybe<Scalars["ID"]>;
  parameters__value?: InputMaybe<Scalars["GenericScalar"]>;
  parameters__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  status__is_protected?: InputMaybe<Scalars["Boolean"]>;
  status__is_visible?: InputMaybe<Scalars["Boolean"]>;
  status__owner__id?: InputMaybe<Scalars["ID"]>;
  status__source__id?: InputMaybe<Scalars["ID"]>;
  status__value?: InputMaybe<Scalars["String"]>;
  status__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  storage_id__is_protected?: InputMaybe<Scalars["Boolean"]>;
  storage_id__is_visible?: InputMaybe<Scalars["Boolean"]>;
  storage_id__owner__id?: InputMaybe<Scalars["ID"]>;
  storage_id__source__id?: InputMaybe<Scalars["ID"]>;
  storage_id__value?: InputMaybe<Scalars["String"]>;
  storage_id__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

/** Network Layer 2 Interface */
export type InfraInterfaceL2Member_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Network Layer 2 Interface */
export type InfraInterfaceL2Subscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Network Layer 2 Interface */
export type InfraInterfaceL2Tagged_VlanArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  role__owner__id?: InputMaybe<Scalars["ID"]>;
  role__source__id?: InputMaybe<Scalars["ID"]>;
  role__value?: InputMaybe<Scalars["String"]>;
  role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  status__is_protected?: InputMaybe<Scalars["Boolean"]>;
  status__is_visible?: InputMaybe<Scalars["Boolean"]>;
  status__owner__id?: InputMaybe<Scalars["ID"]>;
  status__source__id?: InputMaybe<Scalars["ID"]>;
  status__value?: InputMaybe<Scalars["String"]>;
  status__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  vlan_id__is_protected?: InputMaybe<Scalars["Boolean"]>;
  vlan_id__is_visible?: InputMaybe<Scalars["Boolean"]>;
  vlan_id__owner__id?: InputMaybe<Scalars["ID"]>;
  vlan_id__source__id?: InputMaybe<Scalars["ID"]>;
  vlan_id__value?: InputMaybe<Scalars["Int"]>;
  vlan_id__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
};

/** Network Layer 2 Interface */
export type InfraInterfaceL2TagsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Network Layer 2 Interface */
export type InfraInterfaceL2Create = {
  __typename?: "InfraInterfaceL2Create";
  object?: Maybe<InfraInterfaceL2>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type InfraInterfaceL2CreateInput = {
  artifacts?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  connected_endpoint?: InputMaybe<RelatedNodeInput>;
  description?: InputMaybe<TextAttributeInput>;
  device: RelatedNodeInput;
  enabled?: InputMaybe<CheckboxAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  l2_mode: TextAttributeInput;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  mtu?: InputMaybe<NumberAttributeInput>;
  name: TextAttributeInput;
  role?: InputMaybe<TextAttributeInput>;
  speed: NumberAttributeInput;
  status?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  tagged_vlan?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  untagged_vlan?: InputMaybe<RelatedNodeInput>;
};

/** Network Layer 2 Interface */
export type InfraInterfaceL2Delete = {
  __typename?: "InfraInterfaceL2Delete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** Network Layer 2 Interface */
export type InfraInterfaceL2Update = {
  __typename?: "InfraInterfaceL2Update";
  object?: Maybe<InfraInterfaceL2>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type InfraInterfaceL2UpdateInput = {
  artifacts?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  connected_endpoint?: InputMaybe<RelatedNodeInput>;
  description?: InputMaybe<TextAttributeInput>;
  device?: InputMaybe<RelatedNodeInput>;
  enabled?: InputMaybe<CheckboxAttributeInput>;
  id: Scalars["String"];
  l2_mode?: InputMaybe<TextAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  mtu?: InputMaybe<NumberAttributeInput>;
  name?: InputMaybe<TextAttributeInput>;
  role?: InputMaybe<TextAttributeInput>;
  speed?: InputMaybe<NumberAttributeInput>;
  status?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  tagged_vlan?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  untagged_vlan?: InputMaybe<RelatedNodeInput>;
};

/** Network Layer 2 Interface */
export type InfraInterfaceL2Upsert = {
  __typename?: "InfraInterfaceL2Upsert";
  object?: Maybe<InfraInterfaceL2>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** Network Layer 3 Interface */
export type InfraInterfaceL3 = CoreArtifactTarget &
  CoreNode &
  InfraEndpoint &
  InfraInterface & {
    __typename?: "InfraInterfaceL3";
    _updated_at?: Maybe<Scalars["DateTime"]>;
    artifacts?: Maybe<NestedPaginatedCoreArtifact>;
    connected_endpoint?: Maybe<NestedEdgedInfraEndpoint>;
    description?: Maybe<TextAttribute>;
    device?: Maybe<NestedEdgedInfraDevice>;
    display_label?: Maybe<Scalars["String"]>;
    enabled?: Maybe<CheckboxAttribute>;
    id: Scalars["String"];
    ip_addresses?: Maybe<NestedPaginatedInfraIpAddress>;
    member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    mtu?: Maybe<NumberAttribute>;
    name: TextAttribute;
    role?: Maybe<Dropdown>;
    speed: NumberAttribute;
    status?: Maybe<Dropdown>;
    subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    tags?: Maybe<NestedPaginatedBuiltinTag>;
  };

/** Network Layer 3 Interface */
export type InfraInterfaceL3ArtifactsArgs = {
  checksum__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checksum__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checksum__owner__id?: InputMaybe<Scalars["ID"]>;
  checksum__source__id?: InputMaybe<Scalars["ID"]>;
  checksum__value?: InputMaybe<Scalars["String"]>;
  checksum__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  content_type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  content_type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  content_type__owner__id?: InputMaybe<Scalars["ID"]>;
  content_type__source__id?: InputMaybe<Scalars["ID"]>;
  content_type__value?: InputMaybe<Scalars["String"]>;
  content_type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  parameters__is_protected?: InputMaybe<Scalars["Boolean"]>;
  parameters__is_visible?: InputMaybe<Scalars["Boolean"]>;
  parameters__owner__id?: InputMaybe<Scalars["ID"]>;
  parameters__source__id?: InputMaybe<Scalars["ID"]>;
  parameters__value?: InputMaybe<Scalars["GenericScalar"]>;
  parameters__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  status__is_protected?: InputMaybe<Scalars["Boolean"]>;
  status__is_visible?: InputMaybe<Scalars["Boolean"]>;
  status__owner__id?: InputMaybe<Scalars["ID"]>;
  status__source__id?: InputMaybe<Scalars["ID"]>;
  status__value?: InputMaybe<Scalars["String"]>;
  status__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  storage_id__is_protected?: InputMaybe<Scalars["Boolean"]>;
  storage_id__is_visible?: InputMaybe<Scalars["Boolean"]>;
  storage_id__owner__id?: InputMaybe<Scalars["ID"]>;
  storage_id__source__id?: InputMaybe<Scalars["ID"]>;
  storage_id__value?: InputMaybe<Scalars["String"]>;
  storage_id__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

/** Network Layer 3 Interface */
export type InfraInterfaceL3Ip_AddressesArgs = {
  address__is_protected?: InputMaybe<Scalars["Boolean"]>;
  address__is_visible?: InputMaybe<Scalars["Boolean"]>;
  address__owner__id?: InputMaybe<Scalars["ID"]>;
  address__source__id?: InputMaybe<Scalars["ID"]>;
  address__value?: InputMaybe<Scalars["String"]>;
  address__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Network Layer 3 Interface */
export type InfraInterfaceL3Member_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Network Layer 3 Interface */
export type InfraInterfaceL3Subscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Network Layer 3 Interface */
export type InfraInterfaceL3TagsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Network Layer 3 Interface */
export type InfraInterfaceL3Create = {
  __typename?: "InfraInterfaceL3Create";
  object?: Maybe<InfraInterfaceL3>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type InfraInterfaceL3CreateInput = {
  artifacts?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  connected_endpoint?: InputMaybe<RelatedNodeInput>;
  description?: InputMaybe<TextAttributeInput>;
  device: RelatedNodeInput;
  enabled?: InputMaybe<CheckboxAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  ip_addresses?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  mtu?: InputMaybe<NumberAttributeInput>;
  name: TextAttributeInput;
  role?: InputMaybe<TextAttributeInput>;
  speed: NumberAttributeInput;
  status?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** Network Layer 3 Interface */
export type InfraInterfaceL3Delete = {
  __typename?: "InfraInterfaceL3Delete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** Network Layer 3 Interface */
export type InfraInterfaceL3Update = {
  __typename?: "InfraInterfaceL3Update";
  object?: Maybe<InfraInterfaceL3>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type InfraInterfaceL3UpdateInput = {
  artifacts?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  connected_endpoint?: InputMaybe<RelatedNodeInput>;
  description?: InputMaybe<TextAttributeInput>;
  device?: InputMaybe<RelatedNodeInput>;
  enabled?: InputMaybe<CheckboxAttributeInput>;
  id: Scalars["String"];
  ip_addresses?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  mtu?: InputMaybe<NumberAttributeInput>;
  name?: InputMaybe<TextAttributeInput>;
  role?: InputMaybe<TextAttributeInput>;
  speed?: InputMaybe<NumberAttributeInput>;
  status?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** Network Layer 3 Interface */
export type InfraInterfaceL3Upsert = {
  __typename?: "InfraInterfaceL3Upsert";
  object?: Maybe<InfraInterfaceL3>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** Generic hierarchical location */
export type InfraLocation = {
  description?: Maybe<TextAttribute>;
  display_label?: Maybe<Scalars["String"]>;
  /** Unique identifier */
  id?: Maybe<Scalars["String"]>;
  member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  name: TextAttribute;
  subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
};

/** Generic hierarchical location */
export type InfraLocationMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  include_descendants?: InputMaybe<Scalars["Boolean"]>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Generic hierarchical location */
export type InfraLocationSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  include_descendants?: InputMaybe<Scalars["Boolean"]>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A Platform represents the type of software running on a device */
export type InfraPlatform = CoreNode & {
  __typename?: "InfraPlatform";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  ansible_network_os?: Maybe<TextAttribute>;
  description?: Maybe<TextAttribute>;
  devices?: Maybe<NestedPaginatedInfraDevice>;
  display_label?: Maybe<Scalars["String"]>;
  id: Scalars["String"];
  member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  name: TextAttribute;
  napalm_driver?: Maybe<TextAttribute>;
  netmiko_device_type?: Maybe<TextAttribute>;
  nornir_platform?: Maybe<TextAttribute>;
  subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
};

/** A Platform represents the type of software running on a device */
export type InfraPlatformDevicesArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  role__owner__id?: InputMaybe<Scalars["ID"]>;
  role__source__id?: InputMaybe<Scalars["ID"]>;
  role__value?: InputMaybe<Scalars["String"]>;
  role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  status__is_protected?: InputMaybe<Scalars["Boolean"]>;
  status__is_visible?: InputMaybe<Scalars["Boolean"]>;
  status__owner__id?: InputMaybe<Scalars["ID"]>;
  status__source__id?: InputMaybe<Scalars["ID"]>;
  status__value?: InputMaybe<Scalars["String"]>;
  status__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  type__owner__id?: InputMaybe<Scalars["ID"]>;
  type__source__id?: InputMaybe<Scalars["ID"]>;
  type__value?: InputMaybe<Scalars["String"]>;
  type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

/** A Platform represents the type of software running on a device */
export type InfraPlatformMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A Platform represents the type of software running on a device */
export type InfraPlatformSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A Platform represents the type of software running on a device */
export type InfraPlatformCreate = {
  __typename?: "InfraPlatformCreate";
  object?: Maybe<InfraPlatform>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type InfraPlatformCreateInput = {
  ansible_network_os?: InputMaybe<TextAttributeInput>;
  description?: InputMaybe<TextAttributeInput>;
  devices?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  id?: InputMaybe<Scalars["String"]>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name: TextAttributeInput;
  napalm_driver?: InputMaybe<TextAttributeInput>;
  netmiko_device_type?: InputMaybe<TextAttributeInput>;
  nornir_platform?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** A Platform represents the type of software running on a device */
export type InfraPlatformDelete = {
  __typename?: "InfraPlatformDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A Platform represents the type of software running on a device */
export type InfraPlatformUpdate = {
  __typename?: "InfraPlatformUpdate";
  object?: Maybe<InfraPlatform>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type InfraPlatformUpdateInput = {
  ansible_network_os?: InputMaybe<TextAttributeInput>;
  description?: InputMaybe<TextAttributeInput>;
  devices?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  id: Scalars["String"];
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name?: InputMaybe<TextAttributeInput>;
  napalm_driver?: InputMaybe<TextAttributeInput>;
  netmiko_device_type?: InputMaybe<TextAttributeInput>;
  nornir_platform?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** A Platform represents the type of software running on a device */
export type InfraPlatformUpsert = {
  __typename?: "InfraPlatformUpsert";
  object?: Maybe<InfraPlatform>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A site within a country. */
export type InfraSite = CoreNode &
  InfraLocation & {
    __typename?: "InfraSite";
    _updated_at?: Maybe<Scalars["DateTime"]>;
    address?: Maybe<TextAttribute>;
    ancestors?: Maybe<NestedPaginatedInfraLocation>;
    circuit_endpoints?: Maybe<NestedPaginatedInfraCircuitEndpoint>;
    city?: Maybe<TextAttribute>;
    contact?: Maybe<TextAttribute>;
    descendants?: Maybe<NestedPaginatedInfraLocation>;
    description?: Maybe<TextAttribute>;
    devices?: Maybe<NestedPaginatedInfraDevice>;
    display_label?: Maybe<Scalars["String"]>;
    id: Scalars["String"];
    member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    name: TextAttribute;
    parent?: Maybe<NestedEdgedInfraCountry>;
    subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    tags?: Maybe<NestedPaginatedBuiltinTag>;
    vlans?: Maybe<NestedPaginatedInfraVlan>;
  };

/** A site within a country. */
export type InfraSiteAncestorsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A site within a country. */
export type InfraSiteCircuit_EndpointsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  include_descendants?: InputMaybe<Scalars["Boolean"]>;
  limit?: InputMaybe<Scalars["Int"]>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A site within a country. */
export type InfraSiteDescendantsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A site within a country. */
export type InfraSiteDevicesArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  include_descendants?: InputMaybe<Scalars["Boolean"]>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  role__owner__id?: InputMaybe<Scalars["ID"]>;
  role__source__id?: InputMaybe<Scalars["ID"]>;
  role__value?: InputMaybe<Scalars["String"]>;
  role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  status__is_protected?: InputMaybe<Scalars["Boolean"]>;
  status__is_visible?: InputMaybe<Scalars["Boolean"]>;
  status__owner__id?: InputMaybe<Scalars["ID"]>;
  status__source__id?: InputMaybe<Scalars["ID"]>;
  status__value?: InputMaybe<Scalars["String"]>;
  status__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  type__owner__id?: InputMaybe<Scalars["ID"]>;
  type__source__id?: InputMaybe<Scalars["ID"]>;
  type__value?: InputMaybe<Scalars["String"]>;
  type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

/** A site within a country. */
export type InfraSiteMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  include_descendants?: InputMaybe<Scalars["Boolean"]>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A site within a country. */
export type InfraSiteSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  include_descendants?: InputMaybe<Scalars["Boolean"]>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A site within a country. */
export type InfraSiteTagsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  include_descendants?: InputMaybe<Scalars["Boolean"]>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A site within a country. */
export type InfraSiteVlansArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  include_descendants?: InputMaybe<Scalars["Boolean"]>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  role__owner__id?: InputMaybe<Scalars["ID"]>;
  role__source__id?: InputMaybe<Scalars["ID"]>;
  role__value?: InputMaybe<Scalars["String"]>;
  role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  status__is_protected?: InputMaybe<Scalars["Boolean"]>;
  status__is_visible?: InputMaybe<Scalars["Boolean"]>;
  status__owner__id?: InputMaybe<Scalars["ID"]>;
  status__source__id?: InputMaybe<Scalars["ID"]>;
  status__value?: InputMaybe<Scalars["String"]>;
  status__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  vlan_id__is_protected?: InputMaybe<Scalars["Boolean"]>;
  vlan_id__is_visible?: InputMaybe<Scalars["Boolean"]>;
  vlan_id__owner__id?: InputMaybe<Scalars["ID"]>;
  vlan_id__source__id?: InputMaybe<Scalars["ID"]>;
  vlan_id__value?: InputMaybe<Scalars["Int"]>;
  vlan_id__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
};

/** A site within a country. */
export type InfraSiteCreate = {
  __typename?: "InfraSiteCreate";
  object?: Maybe<InfraSite>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type InfraSiteCreateInput = {
  address?: InputMaybe<TextAttributeInput>;
  circuit_endpoints?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  city?: InputMaybe<TextAttributeInput>;
  contact?: InputMaybe<TextAttributeInput>;
  description?: InputMaybe<TextAttributeInput>;
  devices?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  id?: InputMaybe<Scalars["String"]>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name: TextAttributeInput;
  parent?: InputMaybe<RelatedNodeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  vlans?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** A site within a country. */
export type InfraSiteDelete = {
  __typename?: "InfraSiteDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A site within a country. */
export type InfraSiteUpdate = {
  __typename?: "InfraSiteUpdate";
  object?: Maybe<InfraSite>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type InfraSiteUpdateInput = {
  address?: InputMaybe<TextAttributeInput>;
  circuit_endpoints?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  city?: InputMaybe<TextAttributeInput>;
  contact?: InputMaybe<TextAttributeInput>;
  description?: InputMaybe<TextAttributeInput>;
  devices?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  id: Scalars["String"];
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name?: InputMaybe<TextAttributeInput>;
  parent?: InputMaybe<RelatedNodeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  tags?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  vlans?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

/** A site within a country. */
export type InfraSiteUpsert = {
  __typename?: "InfraSiteUpsert";
  object?: Maybe<InfraSite>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A VLAN is a logical grouping of devices in the same broadcast domain */
export type InfraVlan = CoreNode & {
  __typename?: "InfraVLAN";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  description?: Maybe<TextAttribute>;
  display_label?: Maybe<Scalars["String"]>;
  gateway?: Maybe<NestedEdgedInfraInterfaceL3>;
  id: Scalars["String"];
  member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  name: TextAttribute;
  role: Dropdown;
  site?: Maybe<NestedEdgedInfraSite>;
  status: Dropdown;
  subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  vlan_id: NumberAttribute;
};

/** A VLAN is a logical grouping of devices in the same broadcast domain */
export type InfraVlanMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A VLAN is a logical grouping of devices in the same broadcast domain */
export type InfraVlanSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** A VLAN is a logical grouping of devices in the same broadcast domain */
export type InfraVlanCreate = {
  __typename?: "InfraVLANCreate";
  object?: Maybe<InfraVlan>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type InfraVlanCreateInput = {
  description?: InputMaybe<TextAttributeInput>;
  gateway?: InputMaybe<RelatedNodeInput>;
  id?: InputMaybe<Scalars["String"]>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name: TextAttributeInput;
  role: TextAttributeInput;
  site?: InputMaybe<RelatedNodeInput>;
  status: TextAttributeInput;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  vlan_id: NumberAttributeInput;
};

/** A VLAN is a logical grouping of devices in the same broadcast domain */
export type InfraVlanDelete = {
  __typename?: "InfraVLANDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** A VLAN is a logical grouping of devices in the same broadcast domain */
export type InfraVlanUpdate = {
  __typename?: "InfraVLANUpdate";
  object?: Maybe<InfraVlan>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type InfraVlanUpdateInput = {
  description?: InputMaybe<TextAttributeInput>;
  gateway?: InputMaybe<RelatedNodeInput>;
  id: Scalars["String"];
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  name?: InputMaybe<TextAttributeInput>;
  role?: InputMaybe<TextAttributeInput>;
  site?: InputMaybe<RelatedNodeInput>;
  status?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  vlan_id?: InputMaybe<NumberAttributeInput>;
};

/** A VLAN is a logical grouping of devices in the same broadcast domain */
export type InfraVlanUpsert = {
  __typename?: "InfraVLANUpsert";
  object?: Maybe<InfraVlan>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** Token for User Account */
export type InternalAccountToken = CoreNode & {
  __typename?: "InternalAccountToken";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  account?: Maybe<NestedEdgedCoreAccount>;
  display_label?: Maybe<Scalars["String"]>;
  expiration?: Maybe<TextAttribute>;
  id: Scalars["String"];
  member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  name?: Maybe<TextAttribute>;
  subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  token: TextAttribute;
};

/** Token for User Account */
export type InternalAccountTokenMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Token for User Account */
export type InternalAccountTokenSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Refresh Token */
export type InternalRefreshToken = CoreNode & {
  __typename?: "InternalRefreshToken";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  account?: Maybe<NestedEdgedCoreAccount>;
  display_label?: Maybe<Scalars["String"]>;
  expiration: TextAttribute;
  id: Scalars["String"];
  member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
};

/** Refresh Token */
export type InternalRefreshTokenMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Refresh Token */
export type InternalRefreshTokenSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Attribute of type JSON */
export type JsonAttribute = AttributeInterface & {
  __typename?: "JSONAttribute";
  id?: Maybe<Scalars["String"]>;
  is_inherited?: Maybe<Scalars["Boolean"]>;
  is_protected?: Maybe<Scalars["Boolean"]>;
  is_visible?: Maybe<Scalars["Boolean"]>;
  owner?: Maybe<LineageOwner>;
  source?: Maybe<LineageSource>;
  updated_at?: Maybe<Scalars["DateTime"]>;
  value?: Maybe<Scalars["GenericScalar"]>;
};

export type JsonAttributeInput = {
  is_protected?: InputMaybe<Scalars["Boolean"]>;
  is_visible?: InputMaybe<Scalars["Boolean"]>;
  owner?: InputMaybe<Scalars["String"]>;
  source?: InputMaybe<Scalars["String"]>;
  value?: InputMaybe<Scalars["GenericScalar"]>;
};

/** Any Entities that is responsible for some data. */
export type LineageOwner = {
  description?: Maybe<TextAttribute>;
  display_label?: Maybe<Scalars["String"]>;
  /** Unique identifier */
  id?: Maybe<Scalars["String"]>;
  member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  name: TextAttribute;
  subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
};

/** Any Entities that is responsible for some data. */
export type LineageOwnerMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Any Entities that is responsible for some data. */
export type LineageOwnerSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Any Entities that stores or produces data. */
export type LineageSource = {
  description?: Maybe<TextAttribute>;
  display_label?: Maybe<Scalars["String"]>;
  /** Unique identifier */
  id?: Maybe<Scalars["String"]>;
  member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
  name: TextAttribute;
  subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
};

/** Any Entities that stores or produces data. */
export type LineageSourceMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Any Entities that stores or produces data. */
export type LineageSourceSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** Attribute of type List */
export type ListAttribute = AttributeInterface & {
  __typename?: "ListAttribute";
  id?: Maybe<Scalars["String"]>;
  is_inherited?: Maybe<Scalars["Boolean"]>;
  is_protected?: Maybe<Scalars["Boolean"]>;
  is_visible?: Maybe<Scalars["Boolean"]>;
  owner?: Maybe<LineageOwner>;
  source?: Maybe<LineageSource>;
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

export type Mutation = {
  __typename?: "Mutation";
  BranchCreate?: Maybe<BranchCreate>;
  BranchDelete?: Maybe<BranchDelete>;
  BranchMerge?: Maybe<BranchMerge>;
  BranchRebase?: Maybe<BranchRebase>;
  BranchUpdate?: Maybe<BranchUpdate>;
  BranchValidate?: Maybe<BranchValidate>;
  /** Represents the role of an object */
  BuiltinRoleCreate?: Maybe<BuiltinRoleCreate>;
  /** Represents the role of an object */
  BuiltinRoleDelete?: Maybe<BuiltinRoleDelete>;
  /** Represents the role of an object */
  BuiltinRoleUpdate?: Maybe<BuiltinRoleUpdate>;
  /** Represents the role of an object */
  BuiltinRoleUpsert?: Maybe<BuiltinRoleUpsert>;
  /** Status represents the current state of an object: active, maintenance */
  BuiltinStatusCreate?: Maybe<BuiltinStatusCreate>;
  /** Status represents the current state of an object: active, maintenance */
  BuiltinStatusDelete?: Maybe<BuiltinStatusDelete>;
  /** Status represents the current state of an object: active, maintenance */
  BuiltinStatusUpdate?: Maybe<BuiltinStatusUpdate>;
  /** Status represents the current state of an object: active, maintenance */
  BuiltinStatusUpsert?: Maybe<BuiltinStatusUpsert>;
  /** Standard Tag object to attached to other objects to provide some context. */
  BuiltinTagCreate?: Maybe<BuiltinTagCreate>;
  /** Standard Tag object to attached to other objects to provide some context. */
  BuiltinTagDelete?: Maybe<BuiltinTagDelete>;
  /** Standard Tag object to attached to other objects to provide some context. */
  BuiltinTagUpdate?: Maybe<BuiltinTagUpdate>;
  /** Standard Tag object to attached to other objects to provide some context. */
  BuiltinTagUpsert?: Maybe<BuiltinTagUpsert>;
  /** User Account for Infrahub */
  CoreAccountCreate?: Maybe<CoreAccountCreate>;
  /** User Account for Infrahub */
  CoreAccountDelete?: Maybe<CoreAccountDelete>;
  CoreAccountSelfUpdate?: Maybe<CoreAccountSelfUpdate>;
  CoreAccountTokenCreate?: Maybe<CoreAccountTokenCreate>;
  /** User Account for Infrahub */
  CoreAccountUpdate?: Maybe<CoreAccountUpdate>;
  /** User Account for Infrahub */
  CoreAccountUpsert?: Maybe<CoreAccountUpsert>;
  /** A check related to an artifact */
  CoreArtifactCheckCreate?: Maybe<CoreArtifactCheckCreate>;
  /** A check related to an artifact */
  CoreArtifactCheckDelete?: Maybe<CoreArtifactCheckDelete>;
  /** A check related to an artifact */
  CoreArtifactCheckUpdate?: Maybe<CoreArtifactCheckUpdate>;
  /** A check related to an artifact */
  CoreArtifactCheckUpsert?: Maybe<CoreArtifactCheckUpsert>;
  CoreArtifactCreate?: Maybe<CoreArtifactCreate>;
  CoreArtifactDefinitionCreate?: Maybe<CoreArtifactDefinitionCreate>;
  CoreArtifactDefinitionDelete?: Maybe<CoreArtifactDefinitionDelete>;
  CoreArtifactDefinitionUpdate?: Maybe<CoreArtifactDefinitionUpdate>;
  CoreArtifactDefinitionUpsert?: Maybe<CoreArtifactDefinitionUpsert>;
  CoreArtifactDelete?: Maybe<CoreArtifactDelete>;
  /** A thread related to an artifact on a proposed change */
  CoreArtifactThreadCreate?: Maybe<CoreArtifactThreadCreate>;
  /** A thread related to an artifact on a proposed change */
  CoreArtifactThreadDelete?: Maybe<CoreArtifactThreadDelete>;
  /** A thread related to an artifact on a proposed change */
  CoreArtifactThreadUpdate?: Maybe<CoreArtifactThreadUpdate>;
  /** A thread related to an artifact on a proposed change */
  CoreArtifactThreadUpsert?: Maybe<CoreArtifactThreadUpsert>;
  CoreArtifactUpdate?: Maybe<CoreArtifactUpdate>;
  CoreArtifactUpsert?: Maybe<CoreArtifactUpsert>;
  /** A validator related to the artifacts */
  CoreArtifactValidatorCreate?: Maybe<CoreArtifactValidatorCreate>;
  /** A validator related to the artifacts */
  CoreArtifactValidatorDelete?: Maybe<CoreArtifactValidatorDelete>;
  /** A validator related to the artifacts */
  CoreArtifactValidatorUpdate?: Maybe<CoreArtifactValidatorUpdate>;
  /** A validator related to the artifacts */
  CoreArtifactValidatorUpsert?: Maybe<CoreArtifactValidatorUpsert>;
  /** A comment on proposed change */
  CoreChangeCommentCreate?: Maybe<CoreChangeCommentCreate>;
  /** A comment on proposed change */
  CoreChangeCommentDelete?: Maybe<CoreChangeCommentDelete>;
  /** A comment on proposed change */
  CoreChangeCommentUpdate?: Maybe<CoreChangeCommentUpdate>;
  /** A comment on proposed change */
  CoreChangeCommentUpsert?: Maybe<CoreChangeCommentUpsert>;
  /** A thread on proposed change */
  CoreChangeThreadCreate?: Maybe<CoreChangeThreadCreate>;
  /** A thread on proposed change */
  CoreChangeThreadDelete?: Maybe<CoreChangeThreadDelete>;
  /** A thread on proposed change */
  CoreChangeThreadUpdate?: Maybe<CoreChangeThreadUpdate>;
  /** A thread on proposed change */
  CoreChangeThreadUpsert?: Maybe<CoreChangeThreadUpsert>;
  CoreCheckDefinitionCreate?: Maybe<CoreCheckDefinitionCreate>;
  CoreCheckDefinitionDelete?: Maybe<CoreCheckDefinitionDelete>;
  CoreCheckDefinitionUpdate?: Maybe<CoreCheckDefinitionUpdate>;
  CoreCheckDefinitionUpsert?: Maybe<CoreCheckDefinitionUpsert>;
  /** A webhook that connects to an external integration */
  CoreCustomWebhookCreate?: Maybe<CoreCustomWebhookCreate>;
  /** A webhook that connects to an external integration */
  CoreCustomWebhookDelete?: Maybe<CoreCustomWebhookDelete>;
  /** A webhook that connects to an external integration */
  CoreCustomWebhookUpdate?: Maybe<CoreCustomWebhookUpdate>;
  /** A webhook that connects to an external integration */
  CoreCustomWebhookUpsert?: Maybe<CoreCustomWebhookUpsert>;
  /** A check related to some Data */
  CoreDataCheckCreate?: Maybe<CoreDataCheckCreate>;
  /** A check related to some Data */
  CoreDataCheckDelete?: Maybe<CoreDataCheckDelete>;
  /** A check related to some Data */
  CoreDataCheckUpdate?: Maybe<CoreDataCheckUpdate>;
  /** A check related to some Data */
  CoreDataCheckUpsert?: Maybe<CoreDataCheckUpsert>;
  /** A check to validate the data integrity between two branches */
  CoreDataValidatorCreate?: Maybe<CoreDataValidatorCreate>;
  /** A check to validate the data integrity between two branches */
  CoreDataValidatorDelete?: Maybe<CoreDataValidatorDelete>;
  /** A check to validate the data integrity between two branches */
  CoreDataValidatorUpdate?: Maybe<CoreDataValidatorUpdate>;
  /** A check to validate the data integrity between two branches */
  CoreDataValidatorUpsert?: Maybe<CoreDataValidatorUpsert>;
  /** A check related to a file in a Git Repository */
  CoreFileCheckCreate?: Maybe<CoreFileCheckCreate>;
  /** A check related to a file in a Git Repository */
  CoreFileCheckDelete?: Maybe<CoreFileCheckDelete>;
  /** A check related to a file in a Git Repository */
  CoreFileCheckUpdate?: Maybe<CoreFileCheckUpdate>;
  /** A check related to a file in a Git Repository */
  CoreFileCheckUpsert?: Maybe<CoreFileCheckUpsert>;
  /** A thread related to a file on a proposed change */
  CoreFileThreadCreate?: Maybe<CoreFileThreadCreate>;
  /** A thread related to a file on a proposed change */
  CoreFileThreadDelete?: Maybe<CoreFileThreadDelete>;
  /** A thread related to a file on a proposed change */
  CoreFileThreadUpdate?: Maybe<CoreFileThreadUpdate>;
  /** A thread related to a file on a proposed change */
  CoreFileThreadUpsert?: Maybe<CoreFileThreadUpsert>;
  /** A pre-defined GraphQL Query */
  CoreGraphQLQueryCreate?: Maybe<CoreGraphQlQueryCreate>;
  /** A pre-defined GraphQL Query */
  CoreGraphQLQueryDelete?: Maybe<CoreGraphQlQueryDelete>;
  /** Group of nodes associated with a given GraphQLQuery. */
  CoreGraphQLQueryGroupCreate?: Maybe<CoreGraphQlQueryGroupCreate>;
  /** Group of nodes associated with a given GraphQLQuery. */
  CoreGraphQLQueryGroupDelete?: Maybe<CoreGraphQlQueryGroupDelete>;
  /** Group of nodes associated with a given GraphQLQuery. */
  CoreGraphQLQueryGroupUpdate?: Maybe<CoreGraphQlQueryGroupUpdate>;
  /** Group of nodes associated with a given GraphQLQuery. */
  CoreGraphQLQueryGroupUpsert?: Maybe<CoreGraphQlQueryGroupUpsert>;
  /** A pre-defined GraphQL Query */
  CoreGraphQLQueryUpdate?: Maybe<CoreGraphQlQueryUpdate>;
  /** A pre-defined GraphQL Query */
  CoreGraphQLQueryUpsert?: Maybe<CoreGraphQlQueryUpsert>;
  /** A thread related to an object on a proposed change */
  CoreObjectThreadCreate?: Maybe<CoreObjectThreadCreate>;
  /** A thread related to an object on a proposed change */
  CoreObjectThreadDelete?: Maybe<CoreObjectThreadDelete>;
  /** A thread related to an object on a proposed change */
  CoreObjectThreadUpdate?: Maybe<CoreObjectThreadUpdate>;
  /** A thread related to an object on a proposed change */
  CoreObjectThreadUpsert?: Maybe<CoreObjectThreadUpsert>;
  /** An organization represent a legal entity, a company */
  CoreOrganizationCreate?: Maybe<CoreOrganizationCreate>;
  /** An organization represent a legal entity, a company */
  CoreOrganizationDelete?: Maybe<CoreOrganizationDelete>;
  /** An organization represent a legal entity, a company */
  CoreOrganizationUpdate?: Maybe<CoreOrganizationUpdate>;
  /** An organization represent a legal entity, a company */
  CoreOrganizationUpsert?: Maybe<CoreOrganizationUpsert>;
  /** Metadata related to a proposed change */
  CoreProposedChangeCreate?: Maybe<CoreProposedChangeCreate>;
  /** Metadata related to a proposed change */
  CoreProposedChangeDelete?: Maybe<CoreProposedChangeDelete>;
  CoreProposedChangeRunCheck?: Maybe<ProposedChangeRequestRunCheck>;
  /** Metadata related to a proposed change */
  CoreProposedChangeUpdate?: Maybe<CoreProposedChangeUpdate>;
  /** Metadata related to a proposed change */
  CoreProposedChangeUpsert?: Maybe<CoreProposedChangeUpsert>;
  /** A Git Repository integrated with Infrahub, Git-side will not be updated */
  CoreReadOnlyRepositoryCreate?: Maybe<CoreReadOnlyRepositoryCreate>;
  /** A Git Repository integrated with Infrahub, Git-side will not be updated */
  CoreReadOnlyRepositoryDelete?: Maybe<CoreReadOnlyRepositoryDelete>;
  /** A Git Repository integrated with Infrahub, Git-side will not be updated */
  CoreReadOnlyRepositoryUpdate?: Maybe<CoreReadOnlyRepositoryUpdate>;
  /** A Git Repository integrated with Infrahub, Git-side will not be updated */
  CoreReadOnlyRepositoryUpsert?: Maybe<CoreReadOnlyRepositoryUpsert>;
  /** A Git Repository integrated with Infrahub */
  CoreRepositoryCreate?: Maybe<CoreRepositoryCreate>;
  /** A Git Repository integrated with Infrahub */
  CoreRepositoryDelete?: Maybe<CoreRepositoryDelete>;
  /** A Git Repository integrated with Infrahub */
  CoreRepositoryUpdate?: Maybe<CoreRepositoryUpdate>;
  /** A Git Repository integrated with Infrahub */
  CoreRepositoryUpsert?: Maybe<CoreRepositoryUpsert>;
  /** A Validator related to a specific repository */
  CoreRepositoryValidatorCreate?: Maybe<CoreRepositoryValidatorCreate>;
  /** A Validator related to a specific repository */
  CoreRepositoryValidatorDelete?: Maybe<CoreRepositoryValidatorDelete>;
  /** A Validator related to a specific repository */
  CoreRepositoryValidatorUpdate?: Maybe<CoreRepositoryValidatorUpdate>;
  /** A Validator related to a specific repository */
  CoreRepositoryValidatorUpsert?: Maybe<CoreRepositoryValidatorUpsert>;
  /** A check related to the schema */
  CoreSchemaCheckCreate?: Maybe<CoreSchemaCheckCreate>;
  /** A check related to the schema */
  CoreSchemaCheckDelete?: Maybe<CoreSchemaCheckDelete>;
  /** A check related to the schema */
  CoreSchemaCheckUpdate?: Maybe<CoreSchemaCheckUpdate>;
  /** A check related to the schema */
  CoreSchemaCheckUpsert?: Maybe<CoreSchemaCheckUpsert>;
  /** A validator related to the schema */
  CoreSchemaValidatorCreate?: Maybe<CoreSchemaValidatorCreate>;
  /** A validator related to the schema */
  CoreSchemaValidatorDelete?: Maybe<CoreSchemaValidatorDelete>;
  /** A validator related to the schema */
  CoreSchemaValidatorUpdate?: Maybe<CoreSchemaValidatorUpdate>;
  /** A validator related to the schema */
  CoreSchemaValidatorUpsert?: Maybe<CoreSchemaValidatorUpsert>;
  /** A standard check */
  CoreStandardCheckCreate?: Maybe<CoreStandardCheckCreate>;
  /** A standard check */
  CoreStandardCheckDelete?: Maybe<CoreStandardCheckDelete>;
  /** A standard check */
  CoreStandardCheckUpdate?: Maybe<CoreStandardCheckUpdate>;
  /** A standard check */
  CoreStandardCheckUpsert?: Maybe<CoreStandardCheckUpsert>;
  /** Group of nodes of any kind. */
  CoreStandardGroupCreate?: Maybe<CoreStandardGroupCreate>;
  /** Group of nodes of any kind. */
  CoreStandardGroupDelete?: Maybe<CoreStandardGroupDelete>;
  /** Group of nodes of any kind. */
  CoreStandardGroupUpdate?: Maybe<CoreStandardGroupUpdate>;
  /** Group of nodes of any kind. */
  CoreStandardGroupUpsert?: Maybe<CoreStandardGroupUpsert>;
  /** A webhook that connects to an external integration */
  CoreStandardWebhookCreate?: Maybe<CoreStandardWebhookCreate>;
  /** A webhook that connects to an external integration */
  CoreStandardWebhookDelete?: Maybe<CoreStandardWebhookDelete>;
  /** A webhook that connects to an external integration */
  CoreStandardWebhookUpdate?: Maybe<CoreStandardWebhookUpdate>;
  /** A webhook that connects to an external integration */
  CoreStandardWebhookUpsert?: Maybe<CoreStandardWebhookUpsert>;
  /** A comment on thread within a Proposed Change */
  CoreThreadCommentCreate?: Maybe<CoreThreadCommentCreate>;
  /** A comment on thread within a Proposed Change */
  CoreThreadCommentDelete?: Maybe<CoreThreadCommentDelete>;
  /** A comment on thread within a Proposed Change */
  CoreThreadCommentUpdate?: Maybe<CoreThreadCommentUpdate>;
  /** A comment on thread within a Proposed Change */
  CoreThreadCommentUpsert?: Maybe<CoreThreadCommentUpsert>;
  /** A file rendered from a Jinja2 template */
  CoreTransformJinja2Create?: Maybe<CoreTransformJinja2Create>;
  /** A file rendered from a Jinja2 template */
  CoreTransformJinja2Delete?: Maybe<CoreTransformJinja2Delete>;
  /** A file rendered from a Jinja2 template */
  CoreTransformJinja2Update?: Maybe<CoreTransformJinja2Update>;
  /** A file rendered from a Jinja2 template */
  CoreTransformJinja2Upsert?: Maybe<CoreTransformJinja2Upsert>;
  /** A transform function written in Python */
  CoreTransformPythonCreate?: Maybe<CoreTransformPythonCreate>;
  /** A transform function written in Python */
  CoreTransformPythonDelete?: Maybe<CoreTransformPythonDelete>;
  /** A transform function written in Python */
  CoreTransformPythonUpdate?: Maybe<CoreTransformPythonUpdate>;
  /** A transform function written in Python */
  CoreTransformPythonUpsert?: Maybe<CoreTransformPythonUpsert>;
  /** A Validator related to a user defined checks in a repository */
  CoreUserValidatorCreate?: Maybe<CoreUserValidatorCreate>;
  /** A Validator related to a user defined checks in a repository */
  CoreUserValidatorDelete?: Maybe<CoreUserValidatorDelete>;
  /** A Validator related to a user defined checks in a repository */
  CoreUserValidatorUpdate?: Maybe<CoreUserValidatorUpdate>;
  /** A Validator related to a user defined checks in a repository */
  CoreUserValidatorUpsert?: Maybe<CoreUserValidatorUpsert>;
  /** . */
  DemoEdgeFabricCreate?: Maybe<DemoEdgeFabricCreate>;
  /** . */
  DemoEdgeFabricDelete?: Maybe<DemoEdgeFabricDelete>;
  /** . */
  DemoEdgeFabricUpdate?: Maybe<DemoEdgeFabricUpdate>;
  /** . */
  DemoEdgeFabricUpsert?: Maybe<DemoEdgeFabricUpsert>;
  /** An Autonomous System (AS) is a set of Internet routable IP prefixes belonging to a network */
  InfraAutonomousSystemCreate?: Maybe<InfraAutonomousSystemCreate>;
  /** An Autonomous System (AS) is a set of Internet routable IP prefixes belonging to a network */
  InfraAutonomousSystemDelete?: Maybe<InfraAutonomousSystemDelete>;
  /** An Autonomous System (AS) is a set of Internet routable IP prefixes belonging to a network */
  InfraAutonomousSystemUpdate?: Maybe<InfraAutonomousSystemUpdate>;
  /** An Autonomous System (AS) is a set of Internet routable IP prefixes belonging to a network */
  InfraAutonomousSystemUpsert?: Maybe<InfraAutonomousSystemUpsert>;
  /** A BGP Peer Group is used to regroup parameters that are shared across multiple peers */
  InfraBGPPeerGroupCreate?: Maybe<InfraBgpPeerGroupCreate>;
  /** A BGP Peer Group is used to regroup parameters that are shared across multiple peers */
  InfraBGPPeerGroupDelete?: Maybe<InfraBgpPeerGroupDelete>;
  /** A BGP Peer Group is used to regroup parameters that are shared across multiple peers */
  InfraBGPPeerGroupUpdate?: Maybe<InfraBgpPeerGroupUpdate>;
  /** A BGP Peer Group is used to regroup parameters that are shared across multiple peers */
  InfraBGPPeerGroupUpsert?: Maybe<InfraBgpPeerGroupUpsert>;
  /** A BGP Session represent a point to point connection between two routers */
  InfraBGPSessionCreate?: Maybe<InfraBgpSessionCreate>;
  /** A BGP Session represent a point to point connection between two routers */
  InfraBGPSessionDelete?: Maybe<InfraBgpSessionDelete>;
  /** A BGP Session represent a point to point connection between two routers */
  InfraBGPSessionUpdate?: Maybe<InfraBgpSessionUpdate>;
  /** A BGP Session represent a point to point connection between two routers */
  InfraBGPSessionUpsert?: Maybe<InfraBgpSessionUpsert>;
  /** A Circuit represent a single physical link between two locations */
  InfraCircuitCreate?: Maybe<InfraCircuitCreate>;
  /** A Circuit represent a single physical link between two locations */
  InfraCircuitDelete?: Maybe<InfraCircuitDelete>;
  /** A Circuit endpoint is attached to each end of a circuit */
  InfraCircuitEndpointCreate?: Maybe<InfraCircuitEndpointCreate>;
  /** A Circuit endpoint is attached to each end of a circuit */
  InfraCircuitEndpointDelete?: Maybe<InfraCircuitEndpointDelete>;
  /** A Circuit endpoint is attached to each end of a circuit */
  InfraCircuitEndpointUpdate?: Maybe<InfraCircuitEndpointUpdate>;
  /** A Circuit endpoint is attached to each end of a circuit */
  InfraCircuitEndpointUpsert?: Maybe<InfraCircuitEndpointUpsert>;
  /** A Circuit represent a single physical link between two locations */
  InfraCircuitUpdate?: Maybe<InfraCircuitUpdate>;
  /** A Circuit represent a single physical link between two locations */
  InfraCircuitUpsert?: Maybe<InfraCircuitUpsert>;
  /** A continent on planet earth. */
  InfraContinentCreate?: Maybe<InfraContinentCreate>;
  /** A continent on planet earth. */
  InfraContinentDelete?: Maybe<InfraContinentDelete>;
  /** A continent on planet earth. */
  InfraContinentUpdate?: Maybe<InfraContinentUpdate>;
  /** A continent on planet earth. */
  InfraContinentUpsert?: Maybe<InfraContinentUpsert>;
  /** A country within a continent. */
  InfraCountryCreate?: Maybe<InfraCountryCreate>;
  /** A country within a continent. */
  InfraCountryDelete?: Maybe<InfraCountryDelete>;
  /** A country within a continent. */
  InfraCountryUpdate?: Maybe<InfraCountryUpdate>;
  /** A country within a continent. */
  InfraCountryUpsert?: Maybe<InfraCountryUpsert>;
  /** Generic Device object */
  InfraDeviceCreate?: Maybe<InfraDeviceCreate>;
  /** Generic Device object */
  InfraDeviceDelete?: Maybe<InfraDeviceDelete>;
  /** Generic Device object */
  InfraDeviceUpdate?: Maybe<InfraDeviceUpdate>;
  /** Generic Device object */
  InfraDeviceUpsert?: Maybe<InfraDeviceUpsert>;
  /** IP Address */
  InfraIPAddressCreate?: Maybe<InfraIpAddressCreate>;
  /** IP Address */
  InfraIPAddressDelete?: Maybe<InfraIpAddressDelete>;
  /** IP Address */
  InfraIPAddressUpdate?: Maybe<InfraIpAddressUpdate>;
  /** IP Address */
  InfraIPAddressUpsert?: Maybe<InfraIpAddressUpsert>;
  /** Network Layer 2 Interface */
  InfraInterfaceL2Create?: Maybe<InfraInterfaceL2Create>;
  /** Network Layer 2 Interface */
  InfraInterfaceL2Delete?: Maybe<InfraInterfaceL2Delete>;
  /** Network Layer 2 Interface */
  InfraInterfaceL2Update?: Maybe<InfraInterfaceL2Update>;
  /** Network Layer 2 Interface */
  InfraInterfaceL2Upsert?: Maybe<InfraInterfaceL2Upsert>;
  /** Network Layer 3 Interface */
  InfraInterfaceL3Create?: Maybe<InfraInterfaceL3Create>;
  /** Network Layer 3 Interface */
  InfraInterfaceL3Delete?: Maybe<InfraInterfaceL3Delete>;
  /** Network Layer 3 Interface */
  InfraInterfaceL3Update?: Maybe<InfraInterfaceL3Update>;
  /** Network Layer 3 Interface */
  InfraInterfaceL3Upsert?: Maybe<InfraInterfaceL3Upsert>;
  /** A Platform represents the type of software running on a device */
  InfraPlatformCreate?: Maybe<InfraPlatformCreate>;
  /** A Platform represents the type of software running on a device */
  InfraPlatformDelete?: Maybe<InfraPlatformDelete>;
  /** A Platform represents the type of software running on a device */
  InfraPlatformUpdate?: Maybe<InfraPlatformUpdate>;
  /** A Platform represents the type of software running on a device */
  InfraPlatformUpsert?: Maybe<InfraPlatformUpsert>;
  /** A site within a country. */
  InfraSiteCreate?: Maybe<InfraSiteCreate>;
  /** A site within a country. */
  InfraSiteDelete?: Maybe<InfraSiteDelete>;
  /** A site within a country. */
  InfraSiteUpdate?: Maybe<InfraSiteUpdate>;
  /** A site within a country. */
  InfraSiteUpsert?: Maybe<InfraSiteUpsert>;
  /** A VLAN is a logical grouping of devices in the same broadcast domain */
  InfraVLANCreate?: Maybe<InfraVlanCreate>;
  /** A VLAN is a logical grouping of devices in the same broadcast domain */
  InfraVLANDelete?: Maybe<InfraVlanDelete>;
  /** A VLAN is a logical grouping of devices in the same broadcast domain */
  InfraVLANUpdate?: Maybe<InfraVlanUpdate>;
  /** A VLAN is a logical grouping of devices in the same broadcast domain */
  InfraVLANUpsert?: Maybe<InfraVlanUpsert>;
  InfrahubTaskCreate?: Maybe<TaskCreate>;
  InfrahubTaskUpdate?: Maybe<TaskUpdate>;
  RelationshipAdd?: Maybe<RelationshipAdd>;
  RelationshipRemove?: Maybe<RelationshipRemove>;
  SchemaDropdownAdd?: Maybe<SchemaDropdownAdd>;
  SchemaDropdownRemove?: Maybe<SchemaDropdownRemove>;
  SchemaEnumAdd?: Maybe<SchemaEnumAdd>;
  SchemaEnumRemove?: Maybe<SchemaEnumRemove>;
  /** object with all attributes */
  TestAllinoneCreate?: Maybe<TestAllinoneCreate>;
  /** object with all attributes */
  TestAllinoneDelete?: Maybe<TestAllinoneDelete>;
  /** object with all attributes */
  TestAllinoneUpdate?: Maybe<TestAllinoneUpdate>;
  /** object with all attributes */
  TestAllinoneUpsert?: Maybe<TestAllinoneUpsert>;
};

export type MutationBranchCreateArgs = {
  background_execution?: InputMaybe<Scalars["Boolean"]>;
  data: BranchCreateInput;
};

export type MutationBranchDeleteArgs = {
  data: BranchNameInput;
};

export type MutationBranchMergeArgs = {
  data: BranchNameInput;
};

export type MutationBranchRebaseArgs = {
  data: BranchNameInput;
};

export type MutationBranchUpdateArgs = {
  data: BranchUpdateInput;
};

export type MutationBranchValidateArgs = {
  data: BranchNameInput;
};

export type MutationBuiltinRoleCreateArgs = {
  data: BuiltinRoleCreateInput;
};

export type MutationBuiltinRoleDeleteArgs = {
  data: DeleteInput;
};

export type MutationBuiltinRoleUpdateArgs = {
  data: BuiltinRoleUpdateInput;
};

export type MutationBuiltinRoleUpsertArgs = {
  data: BuiltinRoleCreateInput;
};

export type MutationBuiltinStatusCreateArgs = {
  data: BuiltinStatusCreateInput;
};

export type MutationBuiltinStatusDeleteArgs = {
  data: DeleteInput;
};

export type MutationBuiltinStatusUpdateArgs = {
  data: BuiltinStatusUpdateInput;
};

export type MutationBuiltinStatusUpsertArgs = {
  data: BuiltinStatusCreateInput;
};

export type MutationBuiltinTagCreateArgs = {
  data: BuiltinTagCreateInput;
};

export type MutationBuiltinTagDeleteArgs = {
  data: DeleteInput;
};

export type MutationBuiltinTagUpdateArgs = {
  data: BuiltinTagUpdateInput;
};

export type MutationBuiltinTagUpsertArgs = {
  data: BuiltinTagCreateInput;
};

export type MutationCoreAccountCreateArgs = {
  data: CoreAccountCreateInput;
};

export type MutationCoreAccountDeleteArgs = {
  data: DeleteInput;
};

export type MutationCoreAccountSelfUpdateArgs = {
  data: CoreAccountUpdateSelfInput;
};

export type MutationCoreAccountTokenCreateArgs = {
  data: CoreAccountTokenCreateInput;
};

export type MutationCoreAccountUpdateArgs = {
  data: CoreAccountUpdateInput;
};

export type MutationCoreAccountUpsertArgs = {
  data: CoreAccountCreateInput;
};

export type MutationCoreArtifactCheckCreateArgs = {
  data: CoreArtifactCheckCreateInput;
};

export type MutationCoreArtifactCheckDeleteArgs = {
  data: DeleteInput;
};

export type MutationCoreArtifactCheckUpdateArgs = {
  data: CoreArtifactCheckUpdateInput;
};

export type MutationCoreArtifactCheckUpsertArgs = {
  data: CoreArtifactCheckCreateInput;
};

export type MutationCoreArtifactCreateArgs = {
  data: CoreArtifactCreateInput;
};

export type MutationCoreArtifactDefinitionCreateArgs = {
  data: CoreArtifactDefinitionCreateInput;
};

export type MutationCoreArtifactDefinitionDeleteArgs = {
  data: DeleteInput;
};

export type MutationCoreArtifactDefinitionUpdateArgs = {
  data: CoreArtifactDefinitionUpdateInput;
};

export type MutationCoreArtifactDefinitionUpsertArgs = {
  data: CoreArtifactDefinitionCreateInput;
};

export type MutationCoreArtifactDeleteArgs = {
  data: DeleteInput;
};

export type MutationCoreArtifactThreadCreateArgs = {
  data: CoreArtifactThreadCreateInput;
};

export type MutationCoreArtifactThreadDeleteArgs = {
  data: DeleteInput;
};

export type MutationCoreArtifactThreadUpdateArgs = {
  data: CoreArtifactThreadUpdateInput;
};

export type MutationCoreArtifactThreadUpsertArgs = {
  data: CoreArtifactThreadCreateInput;
};

export type MutationCoreArtifactUpdateArgs = {
  data: CoreArtifactUpdateInput;
};

export type MutationCoreArtifactUpsertArgs = {
  data: CoreArtifactCreateInput;
};

export type MutationCoreArtifactValidatorCreateArgs = {
  data: CoreArtifactValidatorCreateInput;
};

export type MutationCoreArtifactValidatorDeleteArgs = {
  data: DeleteInput;
};

export type MutationCoreArtifactValidatorUpdateArgs = {
  data: CoreArtifactValidatorUpdateInput;
};

export type MutationCoreArtifactValidatorUpsertArgs = {
  data: CoreArtifactValidatorCreateInput;
};

export type MutationCoreChangeCommentCreateArgs = {
  data: CoreChangeCommentCreateInput;
};

export type MutationCoreChangeCommentDeleteArgs = {
  data: DeleteInput;
};

export type MutationCoreChangeCommentUpdateArgs = {
  data: CoreChangeCommentUpdateInput;
};

export type MutationCoreChangeCommentUpsertArgs = {
  data: CoreChangeCommentCreateInput;
};

export type MutationCoreChangeThreadCreateArgs = {
  data: CoreChangeThreadCreateInput;
};

export type MutationCoreChangeThreadDeleteArgs = {
  data: DeleteInput;
};

export type MutationCoreChangeThreadUpdateArgs = {
  data: CoreChangeThreadUpdateInput;
};

export type MutationCoreChangeThreadUpsertArgs = {
  data: CoreChangeThreadCreateInput;
};

export type MutationCoreCheckDefinitionCreateArgs = {
  data: CoreCheckDefinitionCreateInput;
};

export type MutationCoreCheckDefinitionDeleteArgs = {
  data: DeleteInput;
};

export type MutationCoreCheckDefinitionUpdateArgs = {
  data: CoreCheckDefinitionUpdateInput;
};

export type MutationCoreCheckDefinitionUpsertArgs = {
  data: CoreCheckDefinitionCreateInput;
};

export type MutationCoreCustomWebhookCreateArgs = {
  data: CoreCustomWebhookCreateInput;
};

export type MutationCoreCustomWebhookDeleteArgs = {
  data: DeleteInput;
};

export type MutationCoreCustomWebhookUpdateArgs = {
  data: CoreCustomWebhookUpdateInput;
};

export type MutationCoreCustomWebhookUpsertArgs = {
  data: CoreCustomWebhookCreateInput;
};

export type MutationCoreDataCheckCreateArgs = {
  data: CoreDataCheckCreateInput;
};

export type MutationCoreDataCheckDeleteArgs = {
  data: DeleteInput;
};

export type MutationCoreDataCheckUpdateArgs = {
  data: CoreDataCheckUpdateInput;
};

export type MutationCoreDataCheckUpsertArgs = {
  data: CoreDataCheckCreateInput;
};

export type MutationCoreDataValidatorCreateArgs = {
  data: CoreDataValidatorCreateInput;
};

export type MutationCoreDataValidatorDeleteArgs = {
  data: DeleteInput;
};

export type MutationCoreDataValidatorUpdateArgs = {
  data: CoreDataValidatorUpdateInput;
};

export type MutationCoreDataValidatorUpsertArgs = {
  data: CoreDataValidatorCreateInput;
};

export type MutationCoreFileCheckCreateArgs = {
  data: CoreFileCheckCreateInput;
};

export type MutationCoreFileCheckDeleteArgs = {
  data: DeleteInput;
};

export type MutationCoreFileCheckUpdateArgs = {
  data: CoreFileCheckUpdateInput;
};

export type MutationCoreFileCheckUpsertArgs = {
  data: CoreFileCheckCreateInput;
};

export type MutationCoreFileThreadCreateArgs = {
  data: CoreFileThreadCreateInput;
};

export type MutationCoreFileThreadDeleteArgs = {
  data: DeleteInput;
};

export type MutationCoreFileThreadUpdateArgs = {
  data: CoreFileThreadUpdateInput;
};

export type MutationCoreFileThreadUpsertArgs = {
  data: CoreFileThreadCreateInput;
};

export type MutationCoreGraphQlQueryCreateArgs = {
  data: CoreGraphQlQueryCreateInput;
};

export type MutationCoreGraphQlQueryDeleteArgs = {
  data: DeleteInput;
};

export type MutationCoreGraphQlQueryGroupCreateArgs = {
  data: CoreGraphQlQueryGroupCreateInput;
};

export type MutationCoreGraphQlQueryGroupDeleteArgs = {
  data: DeleteInput;
};

export type MutationCoreGraphQlQueryGroupUpdateArgs = {
  data: CoreGraphQlQueryGroupUpdateInput;
};

export type MutationCoreGraphQlQueryGroupUpsertArgs = {
  data: CoreGraphQlQueryGroupCreateInput;
};

export type MutationCoreGraphQlQueryUpdateArgs = {
  data: CoreGraphQlQueryUpdateInput;
};

export type MutationCoreGraphQlQueryUpsertArgs = {
  data: CoreGraphQlQueryCreateInput;
};

export type MutationCoreObjectThreadCreateArgs = {
  data: CoreObjectThreadCreateInput;
};

export type MutationCoreObjectThreadDeleteArgs = {
  data: DeleteInput;
};

export type MutationCoreObjectThreadUpdateArgs = {
  data: CoreObjectThreadUpdateInput;
};

export type MutationCoreObjectThreadUpsertArgs = {
  data: CoreObjectThreadCreateInput;
};

export type MutationCoreOrganizationCreateArgs = {
  data: CoreOrganizationCreateInput;
};

export type MutationCoreOrganizationDeleteArgs = {
  data: DeleteInput;
};

export type MutationCoreOrganizationUpdateArgs = {
  data: CoreOrganizationUpdateInput;
};

export type MutationCoreOrganizationUpsertArgs = {
  data: CoreOrganizationCreateInput;
};

export type MutationCoreProposedChangeCreateArgs = {
  data: CoreProposedChangeCreateInput;
};

export type MutationCoreProposedChangeDeleteArgs = {
  data: DeleteInput;
};

export type MutationCoreProposedChangeRunCheckArgs = {
  data: ProposedChangeRequestRunCheckInput;
};

export type MutationCoreProposedChangeUpdateArgs = {
  data: CoreProposedChangeUpdateInput;
};

export type MutationCoreProposedChangeUpsertArgs = {
  data: CoreProposedChangeCreateInput;
};

export type MutationCoreReadOnlyRepositoryCreateArgs = {
  data: CoreReadOnlyRepositoryCreateInput;
};

export type MutationCoreReadOnlyRepositoryDeleteArgs = {
  data: DeleteInput;
};

export type MutationCoreReadOnlyRepositoryUpdateArgs = {
  data: CoreReadOnlyRepositoryUpdateInput;
};

export type MutationCoreReadOnlyRepositoryUpsertArgs = {
  data: CoreReadOnlyRepositoryCreateInput;
};

export type MutationCoreRepositoryCreateArgs = {
  data: CoreRepositoryCreateInput;
};

export type MutationCoreRepositoryDeleteArgs = {
  data: DeleteInput;
};

export type MutationCoreRepositoryUpdateArgs = {
  data: CoreRepositoryUpdateInput;
};

export type MutationCoreRepositoryUpsertArgs = {
  data: CoreRepositoryCreateInput;
};

export type MutationCoreRepositoryValidatorCreateArgs = {
  data: CoreRepositoryValidatorCreateInput;
};

export type MutationCoreRepositoryValidatorDeleteArgs = {
  data: DeleteInput;
};

export type MutationCoreRepositoryValidatorUpdateArgs = {
  data: CoreRepositoryValidatorUpdateInput;
};

export type MutationCoreRepositoryValidatorUpsertArgs = {
  data: CoreRepositoryValidatorCreateInput;
};

export type MutationCoreSchemaCheckCreateArgs = {
  data: CoreSchemaCheckCreateInput;
};

export type MutationCoreSchemaCheckDeleteArgs = {
  data: DeleteInput;
};

export type MutationCoreSchemaCheckUpdateArgs = {
  data: CoreSchemaCheckUpdateInput;
};

export type MutationCoreSchemaCheckUpsertArgs = {
  data: CoreSchemaCheckCreateInput;
};

export type MutationCoreSchemaValidatorCreateArgs = {
  data: CoreSchemaValidatorCreateInput;
};

export type MutationCoreSchemaValidatorDeleteArgs = {
  data: DeleteInput;
};

export type MutationCoreSchemaValidatorUpdateArgs = {
  data: CoreSchemaValidatorUpdateInput;
};

export type MutationCoreSchemaValidatorUpsertArgs = {
  data: CoreSchemaValidatorCreateInput;
};

export type MutationCoreStandardCheckCreateArgs = {
  data: CoreStandardCheckCreateInput;
};

export type MutationCoreStandardCheckDeleteArgs = {
  data: DeleteInput;
};

export type MutationCoreStandardCheckUpdateArgs = {
  data: CoreStandardCheckUpdateInput;
};

export type MutationCoreStandardCheckUpsertArgs = {
  data: CoreStandardCheckCreateInput;
};

export type MutationCoreStandardGroupCreateArgs = {
  data: CoreStandardGroupCreateInput;
};

export type MutationCoreStandardGroupDeleteArgs = {
  data: DeleteInput;
};

export type MutationCoreStandardGroupUpdateArgs = {
  data: CoreStandardGroupUpdateInput;
};

export type MutationCoreStandardGroupUpsertArgs = {
  data: CoreStandardGroupCreateInput;
};

export type MutationCoreStandardWebhookCreateArgs = {
  data: CoreStandardWebhookCreateInput;
};

export type MutationCoreStandardWebhookDeleteArgs = {
  data: DeleteInput;
};

export type MutationCoreStandardWebhookUpdateArgs = {
  data: CoreStandardWebhookUpdateInput;
};

export type MutationCoreStandardWebhookUpsertArgs = {
  data: CoreStandardWebhookCreateInput;
};

export type MutationCoreThreadCommentCreateArgs = {
  data: CoreThreadCommentCreateInput;
};

export type MutationCoreThreadCommentDeleteArgs = {
  data: DeleteInput;
};

export type MutationCoreThreadCommentUpdateArgs = {
  data: CoreThreadCommentUpdateInput;
};

export type MutationCoreThreadCommentUpsertArgs = {
  data: CoreThreadCommentCreateInput;
};

export type MutationCoreTransformJinja2CreateArgs = {
  data: CoreTransformJinja2CreateInput;
};

export type MutationCoreTransformJinja2DeleteArgs = {
  data: DeleteInput;
};

export type MutationCoreTransformJinja2UpdateArgs = {
  data: CoreTransformJinja2UpdateInput;
};

export type MutationCoreTransformJinja2UpsertArgs = {
  data: CoreTransformJinja2CreateInput;
};

export type MutationCoreTransformPythonCreateArgs = {
  data: CoreTransformPythonCreateInput;
};

export type MutationCoreTransformPythonDeleteArgs = {
  data: DeleteInput;
};

export type MutationCoreTransformPythonUpdateArgs = {
  data: CoreTransformPythonUpdateInput;
};

export type MutationCoreTransformPythonUpsertArgs = {
  data: CoreTransformPythonCreateInput;
};

export type MutationCoreUserValidatorCreateArgs = {
  data: CoreUserValidatorCreateInput;
};

export type MutationCoreUserValidatorDeleteArgs = {
  data: DeleteInput;
};

export type MutationCoreUserValidatorUpdateArgs = {
  data: CoreUserValidatorUpdateInput;
};

export type MutationCoreUserValidatorUpsertArgs = {
  data: CoreUserValidatorCreateInput;
};

export type MutationDemoEdgeFabricCreateArgs = {
  data: DemoEdgeFabricCreateInput;
};

export type MutationDemoEdgeFabricDeleteArgs = {
  data: DeleteInput;
};

export type MutationDemoEdgeFabricUpdateArgs = {
  data: DemoEdgeFabricUpdateInput;
};

export type MutationDemoEdgeFabricUpsertArgs = {
  data: DemoEdgeFabricCreateInput;
};

export type MutationInfraAutonomousSystemCreateArgs = {
  data: InfraAutonomousSystemCreateInput;
};

export type MutationInfraAutonomousSystemDeleteArgs = {
  data: DeleteInput;
};

export type MutationInfraAutonomousSystemUpdateArgs = {
  data: InfraAutonomousSystemUpdateInput;
};

export type MutationInfraAutonomousSystemUpsertArgs = {
  data: InfraAutonomousSystemCreateInput;
};

export type MutationInfraBgpPeerGroupCreateArgs = {
  data: InfraBgpPeerGroupCreateInput;
};

export type MutationInfraBgpPeerGroupDeleteArgs = {
  data: DeleteInput;
};

export type MutationInfraBgpPeerGroupUpdateArgs = {
  data: InfraBgpPeerGroupUpdateInput;
};

export type MutationInfraBgpPeerGroupUpsertArgs = {
  data: InfraBgpPeerGroupCreateInput;
};

export type MutationInfraBgpSessionCreateArgs = {
  data: InfraBgpSessionCreateInput;
};

export type MutationInfraBgpSessionDeleteArgs = {
  data: DeleteInput;
};

export type MutationInfraBgpSessionUpdateArgs = {
  data: InfraBgpSessionUpdateInput;
};

export type MutationInfraBgpSessionUpsertArgs = {
  data: InfraBgpSessionCreateInput;
};

export type MutationInfraCircuitCreateArgs = {
  data: InfraCircuitCreateInput;
};

export type MutationInfraCircuitDeleteArgs = {
  data: DeleteInput;
};

export type MutationInfraCircuitEndpointCreateArgs = {
  data: InfraCircuitEndpointCreateInput;
};

export type MutationInfraCircuitEndpointDeleteArgs = {
  data: DeleteInput;
};

export type MutationInfraCircuitEndpointUpdateArgs = {
  data: InfraCircuitEndpointUpdateInput;
};

export type MutationInfraCircuitEndpointUpsertArgs = {
  data: InfraCircuitEndpointCreateInput;
};

export type MutationInfraCircuitUpdateArgs = {
  data: InfraCircuitUpdateInput;
};

export type MutationInfraCircuitUpsertArgs = {
  data: InfraCircuitCreateInput;
};

export type MutationInfraContinentCreateArgs = {
  data: InfraContinentCreateInput;
};

export type MutationInfraContinentDeleteArgs = {
  data: DeleteInput;
};

export type MutationInfraContinentUpdateArgs = {
  data: InfraContinentUpdateInput;
};

export type MutationInfraContinentUpsertArgs = {
  data: InfraContinentCreateInput;
};

export type MutationInfraCountryCreateArgs = {
  data: InfraCountryCreateInput;
};

export type MutationInfraCountryDeleteArgs = {
  data: DeleteInput;
};

export type MutationInfraCountryUpdateArgs = {
  data: InfraCountryUpdateInput;
};

export type MutationInfraCountryUpsertArgs = {
  data: InfraCountryCreateInput;
};

export type MutationInfraDeviceCreateArgs = {
  data: InfraDeviceCreateInput;
};

export type MutationInfraDeviceDeleteArgs = {
  data: DeleteInput;
};

export type MutationInfraDeviceUpdateArgs = {
  data: InfraDeviceUpdateInput;
};

export type MutationInfraDeviceUpsertArgs = {
  data: InfraDeviceCreateInput;
};

export type MutationInfraIpAddressCreateArgs = {
  data: InfraIpAddressCreateInput;
};

export type MutationInfraIpAddressDeleteArgs = {
  data: DeleteInput;
};

export type MutationInfraIpAddressUpdateArgs = {
  data: InfraIpAddressUpdateInput;
};

export type MutationInfraIpAddressUpsertArgs = {
  data: InfraIpAddressCreateInput;
};

export type MutationInfraInterfaceL2CreateArgs = {
  data: InfraInterfaceL2CreateInput;
};

export type MutationInfraInterfaceL2DeleteArgs = {
  data: DeleteInput;
};

export type MutationInfraInterfaceL2UpdateArgs = {
  data: InfraInterfaceL2UpdateInput;
};

export type MutationInfraInterfaceL2UpsertArgs = {
  data: InfraInterfaceL2CreateInput;
};

export type MutationInfraInterfaceL3CreateArgs = {
  data: InfraInterfaceL3CreateInput;
};

export type MutationInfraInterfaceL3DeleteArgs = {
  data: DeleteInput;
};

export type MutationInfraInterfaceL3UpdateArgs = {
  data: InfraInterfaceL3UpdateInput;
};

export type MutationInfraInterfaceL3UpsertArgs = {
  data: InfraInterfaceL3CreateInput;
};

export type MutationInfraPlatformCreateArgs = {
  data: InfraPlatformCreateInput;
};

export type MutationInfraPlatformDeleteArgs = {
  data: DeleteInput;
};

export type MutationInfraPlatformUpdateArgs = {
  data: InfraPlatformUpdateInput;
};

export type MutationInfraPlatformUpsertArgs = {
  data: InfraPlatformCreateInput;
};

export type MutationInfraSiteCreateArgs = {
  data: InfraSiteCreateInput;
};

export type MutationInfraSiteDeleteArgs = {
  data: DeleteInput;
};

export type MutationInfraSiteUpdateArgs = {
  data: InfraSiteUpdateInput;
};

export type MutationInfraSiteUpsertArgs = {
  data: InfraSiteCreateInput;
};

export type MutationInfraVlanCreateArgs = {
  data: InfraVlanCreateInput;
};

export type MutationInfraVlanDeleteArgs = {
  data: DeleteInput;
};

export type MutationInfraVlanUpdateArgs = {
  data: InfraVlanUpdateInput;
};

export type MutationInfraVlanUpsertArgs = {
  data: InfraVlanCreateInput;
};

export type MutationInfrahubTaskCreateArgs = {
  data: TaskCreateInput;
};

export type MutationInfrahubTaskUpdateArgs = {
  data: TaskUpdateInput;
};

export type MutationRelationshipAddArgs = {
  data: RelationshipNodesInput;
};

export type MutationRelationshipRemoveArgs = {
  data: RelationshipNodesInput;
};

export type MutationSchemaDropdownAddArgs = {
  data: SchemaDropdownAddInput;
};

export type MutationSchemaDropdownRemoveArgs = {
  data: SchemaDropdownRemoveInput;
};

export type MutationSchemaEnumAddArgs = {
  data: SchemaEnumInput;
};

export type MutationSchemaEnumRemoveArgs = {
  data: SchemaEnumInput;
};

export type MutationTestAllinoneCreateArgs = {
  data: TestAllinoneCreateInput;
};

export type MutationTestAllinoneDeleteArgs = {
  data: DeleteInput;
};

export type MutationTestAllinoneUpdateArgs = {
  data: TestAllinoneUpdateInput;
};

export type MutationTestAllinoneUpsertArgs = {
  data: TestAllinoneCreateInput;
};

/** Represents the role of an object */
export type NestedEdgedBuiltinRole = {
  __typename?: "NestedEdgedBuiltinRole";
  node?: Maybe<BuiltinRole>;
  properties?: Maybe<RelationshipProperty>;
};

/** Status represents the current state of an object: active, maintenance */
export type NestedEdgedBuiltinStatus = {
  __typename?: "NestedEdgedBuiltinStatus";
  node?: Maybe<BuiltinStatus>;
  properties?: Maybe<RelationshipProperty>;
};

/** Standard Tag object to attached to other objects to provide some context. */
export type NestedEdgedBuiltinTag = {
  __typename?: "NestedEdgedBuiltinTag";
  node?: Maybe<BuiltinTag>;
  properties?: Maybe<RelationshipProperty>;
};

/** User Account for Infrahub */
export type NestedEdgedCoreAccount = {
  __typename?: "NestedEdgedCoreAccount";
  node?: Maybe<CoreAccount>;
  properties?: Maybe<RelationshipProperty>;
};

export type NestedEdgedCoreArtifact = {
  __typename?: "NestedEdgedCoreArtifact";
  node?: Maybe<CoreArtifact>;
  properties?: Maybe<RelationshipProperty>;
};

/** A check related to an artifact */
export type NestedEdgedCoreArtifactCheck = {
  __typename?: "NestedEdgedCoreArtifactCheck";
  node?: Maybe<CoreArtifactCheck>;
  properties?: Maybe<RelationshipProperty>;
};

export type NestedEdgedCoreArtifactDefinition = {
  __typename?: "NestedEdgedCoreArtifactDefinition";
  node?: Maybe<CoreArtifactDefinition>;
  properties?: Maybe<RelationshipProperty>;
};

/** Extend a node to be associated with artifacts */
export type NestedEdgedCoreArtifactTarget = {
  __typename?: "NestedEdgedCoreArtifactTarget";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  node?: Maybe<CoreArtifactTarget>;
  properties?: Maybe<RelationshipProperty>;
};

/** A thread related to an artifact on a proposed change */
export type NestedEdgedCoreArtifactThread = {
  __typename?: "NestedEdgedCoreArtifactThread";
  node?: Maybe<CoreArtifactThread>;
  properties?: Maybe<RelationshipProperty>;
};

/** A validator related to the artifacts */
export type NestedEdgedCoreArtifactValidator = {
  __typename?: "NestedEdgedCoreArtifactValidator";
  node?: Maybe<CoreArtifactValidator>;
  properties?: Maybe<RelationshipProperty>;
};

/** A comment on proposed change */
export type NestedEdgedCoreChangeComment = {
  __typename?: "NestedEdgedCoreChangeComment";
  node?: Maybe<CoreChangeComment>;
  properties?: Maybe<RelationshipProperty>;
};

/** A thread on proposed change */
export type NestedEdgedCoreChangeThread = {
  __typename?: "NestedEdgedCoreChangeThread";
  node?: Maybe<CoreChangeThread>;
  properties?: Maybe<RelationshipProperty>;
};

export type NestedEdgedCoreCheck = {
  __typename?: "NestedEdgedCoreCheck";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  node?: Maybe<CoreCheck>;
  properties?: Maybe<RelationshipProperty>;
};

export type NestedEdgedCoreCheckDefinition = {
  __typename?: "NestedEdgedCoreCheckDefinition";
  node?: Maybe<CoreCheckDefinition>;
  properties?: Maybe<RelationshipProperty>;
};

/** A comment on a Proposed Change */
export type NestedEdgedCoreComment = {
  __typename?: "NestedEdgedCoreComment";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  node?: Maybe<CoreComment>;
  properties?: Maybe<RelationshipProperty>;
};

/** A webhook that connects to an external integration */
export type NestedEdgedCoreCustomWebhook = {
  __typename?: "NestedEdgedCoreCustomWebhook";
  node?: Maybe<CoreCustomWebhook>;
  properties?: Maybe<RelationshipProperty>;
};

/** A check related to some Data */
export type NestedEdgedCoreDataCheck = {
  __typename?: "NestedEdgedCoreDataCheck";
  node?: Maybe<CoreDataCheck>;
  properties?: Maybe<RelationshipProperty>;
};

/** A check to validate the data integrity between two branches */
export type NestedEdgedCoreDataValidator = {
  __typename?: "NestedEdgedCoreDataValidator";
  node?: Maybe<CoreDataValidator>;
  properties?: Maybe<RelationshipProperty>;
};

/** A check related to a file in a Git Repository */
export type NestedEdgedCoreFileCheck = {
  __typename?: "NestedEdgedCoreFileCheck";
  node?: Maybe<CoreFileCheck>;
  properties?: Maybe<RelationshipProperty>;
};

/** A thread related to a file on a proposed change */
export type NestedEdgedCoreFileThread = {
  __typename?: "NestedEdgedCoreFileThread";
  node?: Maybe<CoreFileThread>;
  properties?: Maybe<RelationshipProperty>;
};

/** A Git Repository integrated with Infrahub */
export type NestedEdgedCoreGenericRepository = {
  __typename?: "NestedEdgedCoreGenericRepository";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  node?: Maybe<CoreGenericRepository>;
  properties?: Maybe<RelationshipProperty>;
};

/** A pre-defined GraphQL Query */
export type NestedEdgedCoreGraphQlQuery = {
  __typename?: "NestedEdgedCoreGraphQLQuery";
  node?: Maybe<CoreGraphQlQuery>;
  properties?: Maybe<RelationshipProperty>;
};

/** Group of nodes associated with a given GraphQLQuery. */
export type NestedEdgedCoreGraphQlQueryGroup = {
  __typename?: "NestedEdgedCoreGraphQLQueryGroup";
  node?: Maybe<CoreGraphQlQueryGroup>;
  properties?: Maybe<RelationshipProperty>;
};

/** Generic Group Object. */
export type NestedEdgedCoreGroup = {
  __typename?: "NestedEdgedCoreGroup";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  node?: Maybe<CoreGroup>;
  properties?: Maybe<RelationshipProperty>;
};

/** Base Node in Infrahub. */
export type NestedEdgedCoreNode = {
  __typename?: "NestedEdgedCoreNode";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  node?: Maybe<CoreNode>;
  properties?: Maybe<RelationshipProperty>;
};

/** A thread related to an object on a proposed change */
export type NestedEdgedCoreObjectThread = {
  __typename?: "NestedEdgedCoreObjectThread";
  node?: Maybe<CoreObjectThread>;
  properties?: Maybe<RelationshipProperty>;
};

/** An organization represent a legal entity, a company */
export type NestedEdgedCoreOrganization = {
  __typename?: "NestedEdgedCoreOrganization";
  node?: Maybe<CoreOrganization>;
  properties?: Maybe<RelationshipProperty>;
};

/** Metadata related to a proposed change */
export type NestedEdgedCoreProposedChange = {
  __typename?: "NestedEdgedCoreProposedChange";
  node?: Maybe<CoreProposedChange>;
  properties?: Maybe<RelationshipProperty>;
};

/** A Git Repository integrated with Infrahub, Git-side will not be updated */
export type NestedEdgedCoreReadOnlyRepository = {
  __typename?: "NestedEdgedCoreReadOnlyRepository";
  node?: Maybe<CoreReadOnlyRepository>;
  properties?: Maybe<RelationshipProperty>;
};

/** A Git Repository integrated with Infrahub */
export type NestedEdgedCoreRepository = {
  __typename?: "NestedEdgedCoreRepository";
  node?: Maybe<CoreRepository>;
  properties?: Maybe<RelationshipProperty>;
};

/** A Validator related to a specific repository */
export type NestedEdgedCoreRepositoryValidator = {
  __typename?: "NestedEdgedCoreRepositoryValidator";
  node?: Maybe<CoreRepositoryValidator>;
  properties?: Maybe<RelationshipProperty>;
};

/** A check related to the schema */
export type NestedEdgedCoreSchemaCheck = {
  __typename?: "NestedEdgedCoreSchemaCheck";
  node?: Maybe<CoreSchemaCheck>;
  properties?: Maybe<RelationshipProperty>;
};

/** A validator related to the schema */
export type NestedEdgedCoreSchemaValidator = {
  __typename?: "NestedEdgedCoreSchemaValidator";
  node?: Maybe<CoreSchemaValidator>;
  properties?: Maybe<RelationshipProperty>;
};

/** A standard check */
export type NestedEdgedCoreStandardCheck = {
  __typename?: "NestedEdgedCoreStandardCheck";
  node?: Maybe<CoreStandardCheck>;
  properties?: Maybe<RelationshipProperty>;
};

/** Group of nodes of any kind. */
export type NestedEdgedCoreStandardGroup = {
  __typename?: "NestedEdgedCoreStandardGroup";
  node?: Maybe<CoreStandardGroup>;
  properties?: Maybe<RelationshipProperty>;
};

/** A webhook that connects to an external integration */
export type NestedEdgedCoreStandardWebhook = {
  __typename?: "NestedEdgedCoreStandardWebhook";
  node?: Maybe<CoreStandardWebhook>;
  properties?: Maybe<RelationshipProperty>;
};

/** Extend a node to be associated with tasks */
export type NestedEdgedCoreTaskTarget = {
  __typename?: "NestedEdgedCoreTaskTarget";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  node?: Maybe<CoreTaskTarget>;
  properties?: Maybe<RelationshipProperty>;
};

/** A thread on a Proposed Change */
export type NestedEdgedCoreThread = {
  __typename?: "NestedEdgedCoreThread";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  node?: Maybe<CoreThread>;
  properties?: Maybe<RelationshipProperty>;
};

/** A comment on thread within a Proposed Change */
export type NestedEdgedCoreThreadComment = {
  __typename?: "NestedEdgedCoreThreadComment";
  node?: Maybe<CoreThreadComment>;
  properties?: Maybe<RelationshipProperty>;
};

/** A file rendered from a Jinja2 template */
export type NestedEdgedCoreTransformJinja2 = {
  __typename?: "NestedEdgedCoreTransformJinja2";
  node?: Maybe<CoreTransformJinja2>;
  properties?: Maybe<RelationshipProperty>;
};

/** A transform function written in Python */
export type NestedEdgedCoreTransformPython = {
  __typename?: "NestedEdgedCoreTransformPython";
  node?: Maybe<CoreTransformPython>;
  properties?: Maybe<RelationshipProperty>;
};

/** Generic Transformation Object. */
export type NestedEdgedCoreTransformation = {
  __typename?: "NestedEdgedCoreTransformation";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  node?: Maybe<CoreTransformation>;
  properties?: Maybe<RelationshipProperty>;
};

/** A Validator related to a user defined checks in a repository */
export type NestedEdgedCoreUserValidator = {
  __typename?: "NestedEdgedCoreUserValidator";
  node?: Maybe<CoreUserValidator>;
  properties?: Maybe<RelationshipProperty>;
};

export type NestedEdgedCoreValidator = {
  __typename?: "NestedEdgedCoreValidator";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  node?: Maybe<CoreValidator>;
  properties?: Maybe<RelationshipProperty>;
};

/** A webhook that connects to an external integration */
export type NestedEdgedCoreWebhook = {
  __typename?: "NestedEdgedCoreWebhook";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  node?: Maybe<CoreWebhook>;
  properties?: Maybe<RelationshipProperty>;
};

/** . */
export type NestedEdgedDemoEdgeFabric = {
  __typename?: "NestedEdgedDemoEdgeFabric";
  node?: Maybe<DemoEdgeFabric>;
  properties?: Maybe<RelationshipProperty>;
};

/** An Autonomous System (AS) is a set of Internet routable IP prefixes belonging to a network */
export type NestedEdgedInfraAutonomousSystem = {
  __typename?: "NestedEdgedInfraAutonomousSystem";
  node?: Maybe<InfraAutonomousSystem>;
  properties?: Maybe<RelationshipProperty>;
};

/** A BGP Peer Group is used to regroup parameters that are shared across multiple peers */
export type NestedEdgedInfraBgpPeerGroup = {
  __typename?: "NestedEdgedInfraBGPPeerGroup";
  node?: Maybe<InfraBgpPeerGroup>;
  properties?: Maybe<RelationshipProperty>;
};

/** A BGP Session represent a point to point connection between two routers */
export type NestedEdgedInfraBgpSession = {
  __typename?: "NestedEdgedInfraBGPSession";
  node?: Maybe<InfraBgpSession>;
  properties?: Maybe<RelationshipProperty>;
};

/** A Circuit represent a single physical link between two locations */
export type NestedEdgedInfraCircuit = {
  __typename?: "NestedEdgedInfraCircuit";
  node?: Maybe<InfraCircuit>;
  properties?: Maybe<RelationshipProperty>;
};

/** A Circuit endpoint is attached to each end of a circuit */
export type NestedEdgedInfraCircuitEndpoint = {
  __typename?: "NestedEdgedInfraCircuitEndpoint";
  node?: Maybe<InfraCircuitEndpoint>;
  properties?: Maybe<RelationshipProperty>;
};

/** A continent on planet earth. */
export type NestedEdgedInfraContinent = {
  __typename?: "NestedEdgedInfraContinent";
  node?: Maybe<InfraContinent>;
  properties?: Maybe<RelationshipProperty>;
};

/** A country within a continent. */
export type NestedEdgedInfraCountry = {
  __typename?: "NestedEdgedInfraCountry";
  node?: Maybe<InfraCountry>;
  properties?: Maybe<RelationshipProperty>;
};

/** Generic Device object */
export type NestedEdgedInfraDevice = {
  __typename?: "NestedEdgedInfraDevice";
  node?: Maybe<InfraDevice>;
  properties?: Maybe<RelationshipProperty>;
};

/** Generic Endpoint to connect two objects together */
export type NestedEdgedInfraEndpoint = {
  __typename?: "NestedEdgedInfraEndpoint";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  node?: Maybe<InfraEndpoint>;
  properties?: Maybe<RelationshipProperty>;
};

/** IP Address */
export type NestedEdgedInfraIpAddress = {
  __typename?: "NestedEdgedInfraIPAddress";
  node?: Maybe<InfraIpAddress>;
  properties?: Maybe<RelationshipProperty>;
};

/** Generic Network Interface */
export type NestedEdgedInfraInterface = {
  __typename?: "NestedEdgedInfraInterface";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  node?: Maybe<InfraInterface>;
  properties?: Maybe<RelationshipProperty>;
};

/** Network Layer 2 Interface */
export type NestedEdgedInfraInterfaceL2 = {
  __typename?: "NestedEdgedInfraInterfaceL2";
  node?: Maybe<InfraInterfaceL2>;
  properties?: Maybe<RelationshipProperty>;
};

/** Network Layer 3 Interface */
export type NestedEdgedInfraInterfaceL3 = {
  __typename?: "NestedEdgedInfraInterfaceL3";
  node?: Maybe<InfraInterfaceL3>;
  properties?: Maybe<RelationshipProperty>;
};

/** Generic hierarchical location */
export type NestedEdgedInfraLocation = {
  __typename?: "NestedEdgedInfraLocation";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  node?: Maybe<InfraLocation>;
  properties?: Maybe<RelationshipProperty>;
};

/** A Platform represents the type of software running on a device */
export type NestedEdgedInfraPlatform = {
  __typename?: "NestedEdgedInfraPlatform";
  node?: Maybe<InfraPlatform>;
  properties?: Maybe<RelationshipProperty>;
};

/** A site within a country. */
export type NestedEdgedInfraSite = {
  __typename?: "NestedEdgedInfraSite";
  node?: Maybe<InfraSite>;
  properties?: Maybe<RelationshipProperty>;
};

/** A VLAN is a logical grouping of devices in the same broadcast domain */
export type NestedEdgedInfraVlan = {
  __typename?: "NestedEdgedInfraVLAN";
  node?: Maybe<InfraVlan>;
  properties?: Maybe<RelationshipProperty>;
};

/** Token for User Account */
export type NestedEdgedInternalAccountToken = {
  __typename?: "NestedEdgedInternalAccountToken";
  node?: Maybe<InternalAccountToken>;
  properties?: Maybe<RelationshipProperty>;
};

/** Refresh Token */
export type NestedEdgedInternalRefreshToken = {
  __typename?: "NestedEdgedInternalRefreshToken";
  node?: Maybe<InternalRefreshToken>;
  properties?: Maybe<RelationshipProperty>;
};

/** Any Entities that is responsible for some data. */
export type NestedEdgedLineageOwner = {
  __typename?: "NestedEdgedLineageOwner";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  node?: Maybe<LineageOwner>;
  properties?: Maybe<RelationshipProperty>;
};

/** Any Entities that stores or produces data. */
export type NestedEdgedLineageSource = {
  __typename?: "NestedEdgedLineageSource";
  _updated_at?: Maybe<Scalars["DateTime"]>;
  node?: Maybe<LineageSource>;
  properties?: Maybe<RelationshipProperty>;
};

/** object with all attributes */
export type NestedEdgedTestAllinone = {
  __typename?: "NestedEdgedTestAllinone";
  node?: Maybe<TestAllinone>;
  properties?: Maybe<RelationshipProperty>;
};

/** Represents the role of an object */
export type NestedPaginatedBuiltinRole = {
  __typename?: "NestedPaginatedBuiltinRole";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedBuiltinRole>>>;
};

/** Status represents the current state of an object: active, maintenance */
export type NestedPaginatedBuiltinStatus = {
  __typename?: "NestedPaginatedBuiltinStatus";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedBuiltinStatus>>>;
};

/** Standard Tag object to attached to other objects to provide some context. */
export type NestedPaginatedBuiltinTag = {
  __typename?: "NestedPaginatedBuiltinTag";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedBuiltinTag>>>;
};

/** User Account for Infrahub */
export type NestedPaginatedCoreAccount = {
  __typename?: "NestedPaginatedCoreAccount";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreAccount>>>;
};

export type NestedPaginatedCoreArtifact = {
  __typename?: "NestedPaginatedCoreArtifact";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreArtifact>>>;
};

/** A check related to an artifact */
export type NestedPaginatedCoreArtifactCheck = {
  __typename?: "NestedPaginatedCoreArtifactCheck";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreArtifactCheck>>>;
};

export type NestedPaginatedCoreArtifactDefinition = {
  __typename?: "NestedPaginatedCoreArtifactDefinition";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreArtifactDefinition>>>;
};

/** Extend a node to be associated with artifacts */
export type NestedPaginatedCoreArtifactTarget = {
  __typename?: "NestedPaginatedCoreArtifactTarget";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreArtifactTarget>>>;
};

/** A thread related to an artifact on a proposed change */
export type NestedPaginatedCoreArtifactThread = {
  __typename?: "NestedPaginatedCoreArtifactThread";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreArtifactThread>>>;
};

/** A validator related to the artifacts */
export type NestedPaginatedCoreArtifactValidator = {
  __typename?: "NestedPaginatedCoreArtifactValidator";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreArtifactValidator>>>;
};

/** A comment on proposed change */
export type NestedPaginatedCoreChangeComment = {
  __typename?: "NestedPaginatedCoreChangeComment";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreChangeComment>>>;
};

/** A thread on proposed change */
export type NestedPaginatedCoreChangeThread = {
  __typename?: "NestedPaginatedCoreChangeThread";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreChangeThread>>>;
};

export type NestedPaginatedCoreCheck = {
  __typename?: "NestedPaginatedCoreCheck";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreCheck>>>;
};

export type NestedPaginatedCoreCheckDefinition = {
  __typename?: "NestedPaginatedCoreCheckDefinition";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreCheckDefinition>>>;
};

/** A comment on a Proposed Change */
export type NestedPaginatedCoreComment = {
  __typename?: "NestedPaginatedCoreComment";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreComment>>>;
};

/** A webhook that connects to an external integration */
export type NestedPaginatedCoreCustomWebhook = {
  __typename?: "NestedPaginatedCoreCustomWebhook";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreCustomWebhook>>>;
};

/** A check related to some Data */
export type NestedPaginatedCoreDataCheck = {
  __typename?: "NestedPaginatedCoreDataCheck";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreDataCheck>>>;
};

/** A check to validate the data integrity between two branches */
export type NestedPaginatedCoreDataValidator = {
  __typename?: "NestedPaginatedCoreDataValidator";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreDataValidator>>>;
};

/** A check related to a file in a Git Repository */
export type NestedPaginatedCoreFileCheck = {
  __typename?: "NestedPaginatedCoreFileCheck";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreFileCheck>>>;
};

/** A thread related to a file on a proposed change */
export type NestedPaginatedCoreFileThread = {
  __typename?: "NestedPaginatedCoreFileThread";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreFileThread>>>;
};

/** A Git Repository integrated with Infrahub */
export type NestedPaginatedCoreGenericRepository = {
  __typename?: "NestedPaginatedCoreGenericRepository";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreGenericRepository>>>;
};

/** A pre-defined GraphQL Query */
export type NestedPaginatedCoreGraphQlQuery = {
  __typename?: "NestedPaginatedCoreGraphQLQuery";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreGraphQlQuery>>>;
};

/** Group of nodes associated with a given GraphQLQuery. */
export type NestedPaginatedCoreGraphQlQueryGroup = {
  __typename?: "NestedPaginatedCoreGraphQLQueryGroup";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreGraphQlQueryGroup>>>;
};

/** Generic Group Object. */
export type NestedPaginatedCoreGroup = {
  __typename?: "NestedPaginatedCoreGroup";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreGroup>>>;
};

/** Base Node in Infrahub. */
export type NestedPaginatedCoreNode = {
  __typename?: "NestedPaginatedCoreNode";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreNode>>>;
};

/** A thread related to an object on a proposed change */
export type NestedPaginatedCoreObjectThread = {
  __typename?: "NestedPaginatedCoreObjectThread";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreObjectThread>>>;
};

/** An organization represent a legal entity, a company */
export type NestedPaginatedCoreOrganization = {
  __typename?: "NestedPaginatedCoreOrganization";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreOrganization>>>;
};

/** Metadata related to a proposed change */
export type NestedPaginatedCoreProposedChange = {
  __typename?: "NestedPaginatedCoreProposedChange";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreProposedChange>>>;
};

/** A Git Repository integrated with Infrahub, Git-side will not be updated */
export type NestedPaginatedCoreReadOnlyRepository = {
  __typename?: "NestedPaginatedCoreReadOnlyRepository";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreReadOnlyRepository>>>;
};

/** A Git Repository integrated with Infrahub */
export type NestedPaginatedCoreRepository = {
  __typename?: "NestedPaginatedCoreRepository";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreRepository>>>;
};

/** A Validator related to a specific repository */
export type NestedPaginatedCoreRepositoryValidator = {
  __typename?: "NestedPaginatedCoreRepositoryValidator";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreRepositoryValidator>>>;
};

/** A check related to the schema */
export type NestedPaginatedCoreSchemaCheck = {
  __typename?: "NestedPaginatedCoreSchemaCheck";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreSchemaCheck>>>;
};

/** A validator related to the schema */
export type NestedPaginatedCoreSchemaValidator = {
  __typename?: "NestedPaginatedCoreSchemaValidator";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreSchemaValidator>>>;
};

/** A standard check */
export type NestedPaginatedCoreStandardCheck = {
  __typename?: "NestedPaginatedCoreStandardCheck";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreStandardCheck>>>;
};

/** Group of nodes of any kind. */
export type NestedPaginatedCoreStandardGroup = {
  __typename?: "NestedPaginatedCoreStandardGroup";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreStandardGroup>>>;
};

/** A webhook that connects to an external integration */
export type NestedPaginatedCoreStandardWebhook = {
  __typename?: "NestedPaginatedCoreStandardWebhook";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreStandardWebhook>>>;
};

/** Extend a node to be associated with tasks */
export type NestedPaginatedCoreTaskTarget = {
  __typename?: "NestedPaginatedCoreTaskTarget";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreTaskTarget>>>;
};

/** A thread on a Proposed Change */
export type NestedPaginatedCoreThread = {
  __typename?: "NestedPaginatedCoreThread";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreThread>>>;
};

/** A comment on thread within a Proposed Change */
export type NestedPaginatedCoreThreadComment = {
  __typename?: "NestedPaginatedCoreThreadComment";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreThreadComment>>>;
};

/** A file rendered from a Jinja2 template */
export type NestedPaginatedCoreTransformJinja2 = {
  __typename?: "NestedPaginatedCoreTransformJinja2";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreTransformJinja2>>>;
};

/** A transform function written in Python */
export type NestedPaginatedCoreTransformPython = {
  __typename?: "NestedPaginatedCoreTransformPython";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreTransformPython>>>;
};

/** Generic Transformation Object. */
export type NestedPaginatedCoreTransformation = {
  __typename?: "NestedPaginatedCoreTransformation";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreTransformation>>>;
};

/** A Validator related to a user defined checks in a repository */
export type NestedPaginatedCoreUserValidator = {
  __typename?: "NestedPaginatedCoreUserValidator";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreUserValidator>>>;
};

export type NestedPaginatedCoreValidator = {
  __typename?: "NestedPaginatedCoreValidator";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreValidator>>>;
};

/** A webhook that connects to an external integration */
export type NestedPaginatedCoreWebhook = {
  __typename?: "NestedPaginatedCoreWebhook";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedCoreWebhook>>>;
};

/** . */
export type NestedPaginatedDemoEdgeFabric = {
  __typename?: "NestedPaginatedDemoEdgeFabric";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedDemoEdgeFabric>>>;
};

/** An Autonomous System (AS) is a set of Internet routable IP prefixes belonging to a network */
export type NestedPaginatedInfraAutonomousSystem = {
  __typename?: "NestedPaginatedInfraAutonomousSystem";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedInfraAutonomousSystem>>>;
};

/** A BGP Peer Group is used to regroup parameters that are shared across multiple peers */
export type NestedPaginatedInfraBgpPeerGroup = {
  __typename?: "NestedPaginatedInfraBGPPeerGroup";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedInfraBgpPeerGroup>>>;
};

/** A BGP Session represent a point to point connection between two routers */
export type NestedPaginatedInfraBgpSession = {
  __typename?: "NestedPaginatedInfraBGPSession";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedInfraBgpSession>>>;
};

/** A Circuit represent a single physical link between two locations */
export type NestedPaginatedInfraCircuit = {
  __typename?: "NestedPaginatedInfraCircuit";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedInfraCircuit>>>;
};

/** A Circuit endpoint is attached to each end of a circuit */
export type NestedPaginatedInfraCircuitEndpoint = {
  __typename?: "NestedPaginatedInfraCircuitEndpoint";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedInfraCircuitEndpoint>>>;
};

/** A continent on planet earth. */
export type NestedPaginatedInfraContinent = {
  __typename?: "NestedPaginatedInfraContinent";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedInfraContinent>>>;
};

/** A country within a continent. */
export type NestedPaginatedInfraCountry = {
  __typename?: "NestedPaginatedInfraCountry";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedInfraCountry>>>;
};

/** Generic Device object */
export type NestedPaginatedInfraDevice = {
  __typename?: "NestedPaginatedInfraDevice";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedInfraDevice>>>;
};

/** Generic Endpoint to connect two objects together */
export type NestedPaginatedInfraEndpoint = {
  __typename?: "NestedPaginatedInfraEndpoint";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedInfraEndpoint>>>;
};

/** IP Address */
export type NestedPaginatedInfraIpAddress = {
  __typename?: "NestedPaginatedInfraIPAddress";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedInfraIpAddress>>>;
};

/** Generic Network Interface */
export type NestedPaginatedInfraInterface = {
  __typename?: "NestedPaginatedInfraInterface";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedInfraInterface>>>;
};

/** Network Layer 2 Interface */
export type NestedPaginatedInfraInterfaceL2 = {
  __typename?: "NestedPaginatedInfraInterfaceL2";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedInfraInterfaceL2>>>;
};

/** Network Layer 3 Interface */
export type NestedPaginatedInfraInterfaceL3 = {
  __typename?: "NestedPaginatedInfraInterfaceL3";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedInfraInterfaceL3>>>;
};

/** Generic hierarchical location */
export type NestedPaginatedInfraLocation = {
  __typename?: "NestedPaginatedInfraLocation";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedInfraLocation>>>;
};

/** A Platform represents the type of software running on a device */
export type NestedPaginatedInfraPlatform = {
  __typename?: "NestedPaginatedInfraPlatform";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedInfraPlatform>>>;
};

/** A site within a country. */
export type NestedPaginatedInfraSite = {
  __typename?: "NestedPaginatedInfraSite";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedInfraSite>>>;
};

/** A VLAN is a logical grouping of devices in the same broadcast domain */
export type NestedPaginatedInfraVlan = {
  __typename?: "NestedPaginatedInfraVLAN";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedInfraVlan>>>;
};

/** Token for User Account */
export type NestedPaginatedInternalAccountToken = {
  __typename?: "NestedPaginatedInternalAccountToken";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedInternalAccountToken>>>;
};

/** Refresh Token */
export type NestedPaginatedInternalRefreshToken = {
  __typename?: "NestedPaginatedInternalRefreshToken";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedInternalRefreshToken>>>;
};

/** Any Entities that is responsible for some data. */
export type NestedPaginatedLineageOwner = {
  __typename?: "NestedPaginatedLineageOwner";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedLineageOwner>>>;
};

/** Any Entities that stores or produces data. */
export type NestedPaginatedLineageSource = {
  __typename?: "NestedPaginatedLineageSource";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedLineageSource>>>;
};

/** object with all attributes */
export type NestedPaginatedTestAllinone = {
  __typename?: "NestedPaginatedTestAllinone";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<NestedEdgedTestAllinone>>>;
};

/** Attribute of type Number */
export type NumberAttribute = AttributeInterface & {
  __typename?: "NumberAttribute";
  id?: Maybe<Scalars["String"]>;
  is_inherited?: Maybe<Scalars["Boolean"]>;
  is_protected?: Maybe<Scalars["Boolean"]>;
  is_visible?: Maybe<Scalars["Boolean"]>;
  owner?: Maybe<LineageOwner>;
  source?: Maybe<LineageSource>;
  updated_at?: Maybe<Scalars["DateTime"]>;
  value?: Maybe<Scalars["Int"]>;
};

export type NumberAttributeInput = {
  is_protected?: InputMaybe<Scalars["Boolean"]>;
  is_visible?: InputMaybe<Scalars["Boolean"]>;
  owner?: InputMaybe<Scalars["String"]>;
  source?: InputMaybe<Scalars["String"]>;
  value?: InputMaybe<Scalars["Int"]>;
};

/** Represents the role of an object */
export type PaginatedBuiltinRole = {
  __typename?: "PaginatedBuiltinRole";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedBuiltinRole>>>;
};

/** Status represents the current state of an object: active, maintenance */
export type PaginatedBuiltinStatus = {
  __typename?: "PaginatedBuiltinStatus";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedBuiltinStatus>>>;
};

/** Standard Tag object to attached to other objects to provide some context. */
export type PaginatedBuiltinTag = {
  __typename?: "PaginatedBuiltinTag";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedBuiltinTag>>>;
};

/** User Account for Infrahub */
export type PaginatedCoreAccount = {
  __typename?: "PaginatedCoreAccount";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreAccount>>>;
};

export type PaginatedCoreArtifact = {
  __typename?: "PaginatedCoreArtifact";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreArtifact>>>;
};

/** A check related to an artifact */
export type PaginatedCoreArtifactCheck = {
  __typename?: "PaginatedCoreArtifactCheck";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreArtifactCheck>>>;
};

export type PaginatedCoreArtifactDefinition = {
  __typename?: "PaginatedCoreArtifactDefinition";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreArtifactDefinition>>>;
};

/** Extend a node to be associated with artifacts */
export type PaginatedCoreArtifactTarget = {
  __typename?: "PaginatedCoreArtifactTarget";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreArtifactTarget>>>;
};

/** A thread related to an artifact on a proposed change */
export type PaginatedCoreArtifactThread = {
  __typename?: "PaginatedCoreArtifactThread";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreArtifactThread>>>;
};

/** A validator related to the artifacts */
export type PaginatedCoreArtifactValidator = {
  __typename?: "PaginatedCoreArtifactValidator";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreArtifactValidator>>>;
};

/** A comment on proposed change */
export type PaginatedCoreChangeComment = {
  __typename?: "PaginatedCoreChangeComment";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreChangeComment>>>;
};

/** A thread on proposed change */
export type PaginatedCoreChangeThread = {
  __typename?: "PaginatedCoreChangeThread";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreChangeThread>>>;
};

export type PaginatedCoreCheck = {
  __typename?: "PaginatedCoreCheck";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreCheck>>>;
};

export type PaginatedCoreCheckDefinition = {
  __typename?: "PaginatedCoreCheckDefinition";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreCheckDefinition>>>;
};

/** A comment on a Proposed Change */
export type PaginatedCoreComment = {
  __typename?: "PaginatedCoreComment";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreComment>>>;
};

/** A webhook that connects to an external integration */
export type PaginatedCoreCustomWebhook = {
  __typename?: "PaginatedCoreCustomWebhook";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreCustomWebhook>>>;
};

/** A check related to some Data */
export type PaginatedCoreDataCheck = {
  __typename?: "PaginatedCoreDataCheck";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreDataCheck>>>;
};

/** A check to validate the data integrity between two branches */
export type PaginatedCoreDataValidator = {
  __typename?: "PaginatedCoreDataValidator";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreDataValidator>>>;
};

/** A check related to a file in a Git Repository */
export type PaginatedCoreFileCheck = {
  __typename?: "PaginatedCoreFileCheck";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreFileCheck>>>;
};

/** A thread related to a file on a proposed change */
export type PaginatedCoreFileThread = {
  __typename?: "PaginatedCoreFileThread";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreFileThread>>>;
};

/** A Git Repository integrated with Infrahub */
export type PaginatedCoreGenericRepository = {
  __typename?: "PaginatedCoreGenericRepository";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreGenericRepository>>>;
};

/** A pre-defined GraphQL Query */
export type PaginatedCoreGraphQlQuery = {
  __typename?: "PaginatedCoreGraphQLQuery";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreGraphQlQuery>>>;
};

/** Group of nodes associated with a given GraphQLQuery. */
export type PaginatedCoreGraphQlQueryGroup = {
  __typename?: "PaginatedCoreGraphQLQueryGroup";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreGraphQlQueryGroup>>>;
};

/** Generic Group Object. */
export type PaginatedCoreGroup = {
  __typename?: "PaginatedCoreGroup";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreGroup>>>;
};

/** Base Node in Infrahub. */
export type PaginatedCoreNode = {
  __typename?: "PaginatedCoreNode";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreNode>>>;
};

/** A thread related to an object on a proposed change */
export type PaginatedCoreObjectThread = {
  __typename?: "PaginatedCoreObjectThread";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreObjectThread>>>;
};

/** An organization represent a legal entity, a company */
export type PaginatedCoreOrganization = {
  __typename?: "PaginatedCoreOrganization";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreOrganization>>>;
};

/** Metadata related to a proposed change */
export type PaginatedCoreProposedChange = {
  __typename?: "PaginatedCoreProposedChange";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreProposedChange>>>;
};

/** A Git Repository integrated with Infrahub, Git-side will not be updated */
export type PaginatedCoreReadOnlyRepository = {
  __typename?: "PaginatedCoreReadOnlyRepository";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreReadOnlyRepository>>>;
};

/** A Git Repository integrated with Infrahub */
export type PaginatedCoreRepository = {
  __typename?: "PaginatedCoreRepository";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreRepository>>>;
};

/** A Validator related to a specific repository */
export type PaginatedCoreRepositoryValidator = {
  __typename?: "PaginatedCoreRepositoryValidator";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreRepositoryValidator>>>;
};

/** A check related to the schema */
export type PaginatedCoreSchemaCheck = {
  __typename?: "PaginatedCoreSchemaCheck";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreSchemaCheck>>>;
};

/** A validator related to the schema */
export type PaginatedCoreSchemaValidator = {
  __typename?: "PaginatedCoreSchemaValidator";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreSchemaValidator>>>;
};

/** A standard check */
export type PaginatedCoreStandardCheck = {
  __typename?: "PaginatedCoreStandardCheck";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreStandardCheck>>>;
};

/** Group of nodes of any kind. */
export type PaginatedCoreStandardGroup = {
  __typename?: "PaginatedCoreStandardGroup";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreStandardGroup>>>;
};

/** A webhook that connects to an external integration */
export type PaginatedCoreStandardWebhook = {
  __typename?: "PaginatedCoreStandardWebhook";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreStandardWebhook>>>;
};

/** Extend a node to be associated with tasks */
export type PaginatedCoreTaskTarget = {
  __typename?: "PaginatedCoreTaskTarget";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreTaskTarget>>>;
};

/** A thread on a Proposed Change */
export type PaginatedCoreThread = {
  __typename?: "PaginatedCoreThread";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreThread>>>;
};

/** A comment on thread within a Proposed Change */
export type PaginatedCoreThreadComment = {
  __typename?: "PaginatedCoreThreadComment";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreThreadComment>>>;
};

/** A file rendered from a Jinja2 template */
export type PaginatedCoreTransformJinja2 = {
  __typename?: "PaginatedCoreTransformJinja2";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreTransformJinja2>>>;
};

/** A transform function written in Python */
export type PaginatedCoreTransformPython = {
  __typename?: "PaginatedCoreTransformPython";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreTransformPython>>>;
};

/** Generic Transformation Object. */
export type PaginatedCoreTransformation = {
  __typename?: "PaginatedCoreTransformation";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreTransformation>>>;
};

/** A Validator related to a user defined checks in a repository */
export type PaginatedCoreUserValidator = {
  __typename?: "PaginatedCoreUserValidator";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreUserValidator>>>;
};

export type PaginatedCoreValidator = {
  __typename?: "PaginatedCoreValidator";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreValidator>>>;
};

/** A webhook that connects to an external integration */
export type PaginatedCoreWebhook = {
  __typename?: "PaginatedCoreWebhook";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedCoreWebhook>>>;
};

/** . */
export type PaginatedDemoEdgeFabric = {
  __typename?: "PaginatedDemoEdgeFabric";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedDemoEdgeFabric>>>;
};

/** An Autonomous System (AS) is a set of Internet routable IP prefixes belonging to a network */
export type PaginatedInfraAutonomousSystem = {
  __typename?: "PaginatedInfraAutonomousSystem";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedInfraAutonomousSystem>>>;
};

/** A BGP Peer Group is used to regroup parameters that are shared across multiple peers */
export type PaginatedInfraBgpPeerGroup = {
  __typename?: "PaginatedInfraBGPPeerGroup";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedInfraBgpPeerGroup>>>;
};

/** A BGP Session represent a point to point connection between two routers */
export type PaginatedInfraBgpSession = {
  __typename?: "PaginatedInfraBGPSession";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedInfraBgpSession>>>;
};

/** A Circuit represent a single physical link between two locations */
export type PaginatedInfraCircuit = {
  __typename?: "PaginatedInfraCircuit";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedInfraCircuit>>>;
};

/** A Circuit endpoint is attached to each end of a circuit */
export type PaginatedInfraCircuitEndpoint = {
  __typename?: "PaginatedInfraCircuitEndpoint";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedInfraCircuitEndpoint>>>;
};

/** A continent on planet earth. */
export type PaginatedInfraContinent = {
  __typename?: "PaginatedInfraContinent";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedInfraContinent>>>;
};

/** A country within a continent. */
export type PaginatedInfraCountry = {
  __typename?: "PaginatedInfraCountry";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedInfraCountry>>>;
};

/** Generic Device object */
export type PaginatedInfraDevice = {
  __typename?: "PaginatedInfraDevice";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedInfraDevice>>>;
};

/** Generic Endpoint to connect two objects together */
export type PaginatedInfraEndpoint = {
  __typename?: "PaginatedInfraEndpoint";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedInfraEndpoint>>>;
};

/** IP Address */
export type PaginatedInfraIpAddress = {
  __typename?: "PaginatedInfraIPAddress";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedInfraIpAddress>>>;
};

/** Generic Network Interface */
export type PaginatedInfraInterface = {
  __typename?: "PaginatedInfraInterface";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedInfraInterface>>>;
};

/** Network Layer 2 Interface */
export type PaginatedInfraInterfaceL2 = {
  __typename?: "PaginatedInfraInterfaceL2";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedInfraInterfaceL2>>>;
};

/** Network Layer 3 Interface */
export type PaginatedInfraInterfaceL3 = {
  __typename?: "PaginatedInfraInterfaceL3";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedInfraInterfaceL3>>>;
};

/** Generic hierarchical location */
export type PaginatedInfraLocation = {
  __typename?: "PaginatedInfraLocation";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedInfraLocation>>>;
};

/** A Platform represents the type of software running on a device */
export type PaginatedInfraPlatform = {
  __typename?: "PaginatedInfraPlatform";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedInfraPlatform>>>;
};

/** A site within a country. */
export type PaginatedInfraSite = {
  __typename?: "PaginatedInfraSite";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedInfraSite>>>;
};

/** A VLAN is a logical grouping of devices in the same broadcast domain */
export type PaginatedInfraVlan = {
  __typename?: "PaginatedInfraVLAN";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedInfraVlan>>>;
};

/** Token for User Account */
export type PaginatedInternalAccountToken = {
  __typename?: "PaginatedInternalAccountToken";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedInternalAccountToken>>>;
};

/** Refresh Token */
export type PaginatedInternalRefreshToken = {
  __typename?: "PaginatedInternalRefreshToken";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedInternalRefreshToken>>>;
};

/** Any Entities that is responsible for some data. */
export type PaginatedLineageOwner = {
  __typename?: "PaginatedLineageOwner";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedLineageOwner>>>;
};

/** Any Entities that stores or produces data. */
export type PaginatedLineageSource = {
  __typename?: "PaginatedLineageSource";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedLineageSource>>>;
};

/** object with all attributes */
export type PaginatedTestAllinone = {
  __typename?: "PaginatedTestAllinone";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<EdgedTestAllinone>>>;
};

export type ProposedChangeRequestRunCheck = {
  __typename?: "ProposedChangeRequestRunCheck";
  ok?: Maybe<Scalars["Boolean"]>;
};

export type ProposedChangeRequestRunCheckInput = {
  check_type?: InputMaybe<CheckType>;
  id: Scalars["String"];
};

export type Query = {
  __typename?: "Query";
  AccountProfile?: Maybe<CoreAccount>;
  Branch?: Maybe<Array<Maybe<Branch>>>;
  BuiltinRole?: Maybe<PaginatedBuiltinRole>;
  BuiltinStatus?: Maybe<PaginatedBuiltinStatus>;
  BuiltinTag?: Maybe<PaginatedBuiltinTag>;
  CoreAccount?: Maybe<PaginatedCoreAccount>;
  CoreArtifact?: Maybe<PaginatedCoreArtifact>;
  CoreArtifactCheck?: Maybe<PaginatedCoreArtifactCheck>;
  CoreArtifactDefinition?: Maybe<PaginatedCoreArtifactDefinition>;
  CoreArtifactTarget?: Maybe<PaginatedCoreArtifactTarget>;
  CoreArtifactThread?: Maybe<PaginatedCoreArtifactThread>;
  CoreArtifactValidator?: Maybe<PaginatedCoreArtifactValidator>;
  CoreChangeComment?: Maybe<PaginatedCoreChangeComment>;
  CoreChangeThread?: Maybe<PaginatedCoreChangeThread>;
  CoreCheck?: Maybe<PaginatedCoreCheck>;
  CoreCheckDefinition?: Maybe<PaginatedCoreCheckDefinition>;
  CoreComment?: Maybe<PaginatedCoreComment>;
  CoreCustomWebhook?: Maybe<PaginatedCoreCustomWebhook>;
  CoreDataCheck?: Maybe<PaginatedCoreDataCheck>;
  CoreDataValidator?: Maybe<PaginatedCoreDataValidator>;
  CoreFileCheck?: Maybe<PaginatedCoreFileCheck>;
  CoreFileThread?: Maybe<PaginatedCoreFileThread>;
  CoreGenericRepository?: Maybe<PaginatedCoreGenericRepository>;
  CoreGraphQLQuery?: Maybe<PaginatedCoreGraphQlQuery>;
  CoreGraphQLQueryGroup?: Maybe<PaginatedCoreGraphQlQueryGroup>;
  CoreGroup?: Maybe<PaginatedCoreGroup>;
  CoreNode?: Maybe<PaginatedCoreNode>;
  CoreObjectThread?: Maybe<PaginatedCoreObjectThread>;
  CoreOrganization?: Maybe<PaginatedCoreOrganization>;
  CoreProposedChange?: Maybe<PaginatedCoreProposedChange>;
  CoreReadOnlyRepository?: Maybe<PaginatedCoreReadOnlyRepository>;
  CoreRepository?: Maybe<PaginatedCoreRepository>;
  CoreRepositoryValidator?: Maybe<PaginatedCoreRepositoryValidator>;
  CoreSchemaCheck?: Maybe<PaginatedCoreSchemaCheck>;
  CoreSchemaValidator?: Maybe<PaginatedCoreSchemaValidator>;
  CoreStandardCheck?: Maybe<PaginatedCoreStandardCheck>;
  CoreStandardGroup?: Maybe<PaginatedCoreStandardGroup>;
  CoreStandardWebhook?: Maybe<PaginatedCoreStandardWebhook>;
  CoreTaskTarget?: Maybe<PaginatedCoreTaskTarget>;
  CoreThread?: Maybe<PaginatedCoreThread>;
  CoreThreadComment?: Maybe<PaginatedCoreThreadComment>;
  CoreTransformJinja2?: Maybe<PaginatedCoreTransformJinja2>;
  CoreTransformPython?: Maybe<PaginatedCoreTransformPython>;
  CoreTransformation?: Maybe<PaginatedCoreTransformation>;
  CoreUserValidator?: Maybe<PaginatedCoreUserValidator>;
  CoreValidator?: Maybe<PaginatedCoreValidator>;
  CoreWebhook?: Maybe<PaginatedCoreWebhook>;
  DemoEdgeFabric?: Maybe<PaginatedDemoEdgeFabric>;
  DiffSummary?: Maybe<Array<Maybe<DiffSummaryEntry>>>;
  DiffSummaryOld?: Maybe<Array<Maybe<DiffSummaryEntryOld>>>;
  InfraAutonomousSystem?: Maybe<PaginatedInfraAutonomousSystem>;
  InfraBGPPeerGroup?: Maybe<PaginatedInfraBgpPeerGroup>;
  InfraBGPSession?: Maybe<PaginatedInfraBgpSession>;
  InfraCircuit?: Maybe<PaginatedInfraCircuit>;
  InfraCircuitEndpoint?: Maybe<PaginatedInfraCircuitEndpoint>;
  InfraContinent?: Maybe<PaginatedInfraContinent>;
  InfraCountry?: Maybe<PaginatedInfraCountry>;
  InfraDevice?: Maybe<PaginatedInfraDevice>;
  InfraEndpoint?: Maybe<PaginatedInfraEndpoint>;
  InfraIPAddress?: Maybe<PaginatedInfraIpAddress>;
  InfraInterface?: Maybe<PaginatedInfraInterface>;
  InfraInterfaceL2?: Maybe<PaginatedInfraInterfaceL2>;
  InfraInterfaceL3?: Maybe<PaginatedInfraInterfaceL3>;
  InfraLocation?: Maybe<PaginatedInfraLocation>;
  InfraPlatform?: Maybe<PaginatedInfraPlatform>;
  InfraSite?: Maybe<PaginatedInfraSite>;
  InfraVLAN?: Maybe<PaginatedInfraVlan>;
  InfrahubInfo?: Maybe<Info>;
  InfrahubTask?: Maybe<Tasks>;
  LineageOwner?: Maybe<PaginatedLineageOwner>;
  LineageSource?: Maybe<PaginatedLineageSource>;
  Relationship?: Maybe<Relationships>;
  TestAllinone?: Maybe<PaginatedTestAllinone>;
};

export type QueryBranchArgs = {
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  name?: InputMaybe<Scalars["String"]>;
};

export type QueryBuiltinRoleArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryBuiltinStatusArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryBuiltinTagArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryCoreAccountArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  password__is_protected?: InputMaybe<Scalars["Boolean"]>;
  password__is_visible?: InputMaybe<Scalars["Boolean"]>;
  password__owner__id?: InputMaybe<Scalars["ID"]>;
  password__source__id?: InputMaybe<Scalars["ID"]>;
  password__value?: InputMaybe<Scalars["String"]>;
  password__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  role__owner__id?: InputMaybe<Scalars["ID"]>;
  role__source__id?: InputMaybe<Scalars["ID"]>;
  role__value?: InputMaybe<Scalars["String"]>;
  role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  type__owner__id?: InputMaybe<Scalars["ID"]>;
  type__source__id?: InputMaybe<Scalars["ID"]>;
  type__value?: InputMaybe<Scalars["String"]>;
  type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryCoreArtifactArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checksum__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checksum__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checksum__owner__id?: InputMaybe<Scalars["ID"]>;
  checksum__source__id?: InputMaybe<Scalars["ID"]>;
  checksum__value?: InputMaybe<Scalars["String"]>;
  checksum__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  content_type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  content_type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  content_type__owner__id?: InputMaybe<Scalars["ID"]>;
  content_type__source__id?: InputMaybe<Scalars["ID"]>;
  content_type__value?: InputMaybe<Scalars["String"]>;
  content_type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  definition__artifact_name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  definition__artifact_name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  definition__artifact_name__owner__id?: InputMaybe<Scalars["ID"]>;
  definition__artifact_name__source__id?: InputMaybe<Scalars["ID"]>;
  definition__artifact_name__value?: InputMaybe<Scalars["String"]>;
  definition__artifact_name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  definition__content_type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  definition__content_type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  definition__content_type__owner__id?: InputMaybe<Scalars["ID"]>;
  definition__content_type__source__id?: InputMaybe<Scalars["ID"]>;
  definition__content_type__value?: InputMaybe<Scalars["String"]>;
  definition__content_type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  definition__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  definition__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  definition__description__owner__id?: InputMaybe<Scalars["ID"]>;
  definition__description__source__id?: InputMaybe<Scalars["ID"]>;
  definition__description__value?: InputMaybe<Scalars["String"]>;
  definition__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  definition__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  definition__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  definition__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  definition__name__owner__id?: InputMaybe<Scalars["ID"]>;
  definition__name__source__id?: InputMaybe<Scalars["ID"]>;
  definition__name__value?: InputMaybe<Scalars["String"]>;
  definition__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  definition__parameters__is_protected?: InputMaybe<Scalars["Boolean"]>;
  definition__parameters__is_visible?: InputMaybe<Scalars["Boolean"]>;
  definition__parameters__owner__id?: InputMaybe<Scalars["ID"]>;
  definition__parameters__source__id?: InputMaybe<Scalars["ID"]>;
  definition__parameters__value?: InputMaybe<Scalars["GenericScalar"]>;
  definition__parameters__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  object__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  parameters__is_protected?: InputMaybe<Scalars["Boolean"]>;
  parameters__is_visible?: InputMaybe<Scalars["Boolean"]>;
  parameters__owner__id?: InputMaybe<Scalars["ID"]>;
  parameters__source__id?: InputMaybe<Scalars["ID"]>;
  parameters__value?: InputMaybe<Scalars["GenericScalar"]>;
  parameters__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  status__is_protected?: InputMaybe<Scalars["Boolean"]>;
  status__is_visible?: InputMaybe<Scalars["Boolean"]>;
  status__owner__id?: InputMaybe<Scalars["ID"]>;
  status__source__id?: InputMaybe<Scalars["ID"]>;
  status__value?: InputMaybe<Scalars["String"]>;
  status__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  storage_id__is_protected?: InputMaybe<Scalars["Boolean"]>;
  storage_id__is_visible?: InputMaybe<Scalars["Boolean"]>;
  storage_id__owner__id?: InputMaybe<Scalars["ID"]>;
  storage_id__source__id?: InputMaybe<Scalars["ID"]>;
  storage_id__value?: InputMaybe<Scalars["String"]>;
  storage_id__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryCoreArtifactCheckArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  artifact_id__is_protected?: InputMaybe<Scalars["Boolean"]>;
  artifact_id__is_visible?: InputMaybe<Scalars["Boolean"]>;
  artifact_id__owner__id?: InputMaybe<Scalars["ID"]>;
  artifact_id__source__id?: InputMaybe<Scalars["ID"]>;
  artifact_id__value?: InputMaybe<Scalars["String"]>;
  artifact_id__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  changed__is_protected?: InputMaybe<Scalars["Boolean"]>;
  changed__is_visible?: InputMaybe<Scalars["Boolean"]>;
  changed__owner__id?: InputMaybe<Scalars["ID"]>;
  changed__source__id?: InputMaybe<Scalars["ID"]>;
  changed__value?: InputMaybe<Scalars["Boolean"]>;
  changed__values?: InputMaybe<Array<InputMaybe<Scalars["Boolean"]>>>;
  checksum__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checksum__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checksum__owner__id?: InputMaybe<Scalars["ID"]>;
  checksum__source__id?: InputMaybe<Scalars["ID"]>;
  checksum__value?: InputMaybe<Scalars["String"]>;
  checksum__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  conclusion__is_protected?: InputMaybe<Scalars["Boolean"]>;
  conclusion__is_visible?: InputMaybe<Scalars["Boolean"]>;
  conclusion__owner__id?: InputMaybe<Scalars["ID"]>;
  conclusion__source__id?: InputMaybe<Scalars["ID"]>;
  conclusion__value?: InputMaybe<Scalars["String"]>;
  conclusion__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  created_at__source__id?: InputMaybe<Scalars["ID"]>;
  created_at__value?: InputMaybe<Scalars["String"]>;
  created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  kind__is_protected?: InputMaybe<Scalars["Boolean"]>;
  kind__is_visible?: InputMaybe<Scalars["Boolean"]>;
  kind__owner__id?: InputMaybe<Scalars["ID"]>;
  kind__source__id?: InputMaybe<Scalars["ID"]>;
  kind__value?: InputMaybe<Scalars["String"]>;
  kind__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  line_number__is_protected?: InputMaybe<Scalars["Boolean"]>;
  line_number__is_visible?: InputMaybe<Scalars["Boolean"]>;
  line_number__owner__id?: InputMaybe<Scalars["ID"]>;
  line_number__source__id?: InputMaybe<Scalars["ID"]>;
  line_number__value?: InputMaybe<Scalars["Int"]>;
  line_number__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  message__is_protected?: InputMaybe<Scalars["Boolean"]>;
  message__is_visible?: InputMaybe<Scalars["Boolean"]>;
  message__owner__id?: InputMaybe<Scalars["ID"]>;
  message__source__id?: InputMaybe<Scalars["ID"]>;
  message__value?: InputMaybe<Scalars["String"]>;
  message__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  origin__is_protected?: InputMaybe<Scalars["Boolean"]>;
  origin__is_visible?: InputMaybe<Scalars["Boolean"]>;
  origin__owner__id?: InputMaybe<Scalars["ID"]>;
  origin__source__id?: InputMaybe<Scalars["ID"]>;
  origin__value?: InputMaybe<Scalars["String"]>;
  origin__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  severity__is_protected?: InputMaybe<Scalars["Boolean"]>;
  severity__is_visible?: InputMaybe<Scalars["Boolean"]>;
  severity__owner__id?: InputMaybe<Scalars["ID"]>;
  severity__source__id?: InputMaybe<Scalars["ID"]>;
  severity__value?: InputMaybe<Scalars["String"]>;
  severity__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  storage_id__is_protected?: InputMaybe<Scalars["Boolean"]>;
  storage_id__is_visible?: InputMaybe<Scalars["Boolean"]>;
  storage_id__owner__id?: InputMaybe<Scalars["ID"]>;
  storage_id__source__id?: InputMaybe<Scalars["ID"]>;
  storage_id__value?: InputMaybe<Scalars["String"]>;
  storage_id__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  validator__completed_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  validator__completed_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  validator__completed_at__owner__id?: InputMaybe<Scalars["ID"]>;
  validator__completed_at__source__id?: InputMaybe<Scalars["ID"]>;
  validator__completed_at__value?: InputMaybe<Scalars["String"]>;
  validator__completed_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  validator__conclusion__is_protected?: InputMaybe<Scalars["Boolean"]>;
  validator__conclusion__is_visible?: InputMaybe<Scalars["Boolean"]>;
  validator__conclusion__owner__id?: InputMaybe<Scalars["ID"]>;
  validator__conclusion__source__id?: InputMaybe<Scalars["ID"]>;
  validator__conclusion__value?: InputMaybe<Scalars["String"]>;
  validator__conclusion__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  validator__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  validator__label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  validator__label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  validator__label__owner__id?: InputMaybe<Scalars["ID"]>;
  validator__label__source__id?: InputMaybe<Scalars["ID"]>;
  validator__label__value?: InputMaybe<Scalars["String"]>;
  validator__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  validator__started_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  validator__started_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  validator__started_at__owner__id?: InputMaybe<Scalars["ID"]>;
  validator__started_at__source__id?: InputMaybe<Scalars["ID"]>;
  validator__started_at__value?: InputMaybe<Scalars["String"]>;
  validator__started_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  validator__state__is_protected?: InputMaybe<Scalars["Boolean"]>;
  validator__state__is_visible?: InputMaybe<Scalars["Boolean"]>;
  validator__state__owner__id?: InputMaybe<Scalars["ID"]>;
  validator__state__source__id?: InputMaybe<Scalars["ID"]>;
  validator__state__value?: InputMaybe<Scalars["String"]>;
  validator__state__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryCoreArtifactDefinitionArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  artifact_name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  artifact_name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  artifact_name__owner__id?: InputMaybe<Scalars["ID"]>;
  artifact_name__source__id?: InputMaybe<Scalars["ID"]>;
  artifact_name__value?: InputMaybe<Scalars["String"]>;
  artifact_name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  content_type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  content_type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  content_type__owner__id?: InputMaybe<Scalars["ID"]>;
  content_type__source__id?: InputMaybe<Scalars["ID"]>;
  content_type__value?: InputMaybe<Scalars["String"]>;
  content_type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  parameters__is_protected?: InputMaybe<Scalars["Boolean"]>;
  parameters__is_visible?: InputMaybe<Scalars["Boolean"]>;
  parameters__owner__id?: InputMaybe<Scalars["ID"]>;
  parameters__source__id?: InputMaybe<Scalars["ID"]>;
  parameters__value?: InputMaybe<Scalars["GenericScalar"]>;
  parameters__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  targets__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  targets__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  targets__description__owner__id?: InputMaybe<Scalars["ID"]>;
  targets__description__source__id?: InputMaybe<Scalars["ID"]>;
  targets__description__value?: InputMaybe<Scalars["String"]>;
  targets__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  targets__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  targets__label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  targets__label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  targets__label__owner__id?: InputMaybe<Scalars["ID"]>;
  targets__label__source__id?: InputMaybe<Scalars["ID"]>;
  targets__label__value?: InputMaybe<Scalars["String"]>;
  targets__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  targets__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  targets__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  targets__name__owner__id?: InputMaybe<Scalars["ID"]>;
  targets__name__source__id?: InputMaybe<Scalars["ID"]>;
  targets__name__value?: InputMaybe<Scalars["String"]>;
  targets__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  transformation__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  transformation__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  transformation__description__owner__id?: InputMaybe<Scalars["ID"]>;
  transformation__description__source__id?: InputMaybe<Scalars["ID"]>;
  transformation__description__value?: InputMaybe<Scalars["String"]>;
  transformation__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  transformation__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  transformation__label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  transformation__label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  transformation__label__owner__id?: InputMaybe<Scalars["ID"]>;
  transformation__label__source__id?: InputMaybe<Scalars["ID"]>;
  transformation__label__value?: InputMaybe<Scalars["String"]>;
  transformation__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  transformation__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  transformation__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  transformation__name__owner__id?: InputMaybe<Scalars["ID"]>;
  transformation__name__source__id?: InputMaybe<Scalars["ID"]>;
  transformation__name__value?: InputMaybe<Scalars["String"]>;
  transformation__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  transformation__timeout__is_protected?: InputMaybe<Scalars["Boolean"]>;
  transformation__timeout__is_visible?: InputMaybe<Scalars["Boolean"]>;
  transformation__timeout__owner__id?: InputMaybe<Scalars["ID"]>;
  transformation__timeout__source__id?: InputMaybe<Scalars["ID"]>;
  transformation__timeout__value?: InputMaybe<Scalars["Int"]>;
  transformation__timeout__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
};

export type QueryCoreArtifactTargetArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  artifacts__checksum__is_protected?: InputMaybe<Scalars["Boolean"]>;
  artifacts__checksum__is_visible?: InputMaybe<Scalars["Boolean"]>;
  artifacts__checksum__owner__id?: InputMaybe<Scalars["ID"]>;
  artifacts__checksum__source__id?: InputMaybe<Scalars["ID"]>;
  artifacts__checksum__value?: InputMaybe<Scalars["String"]>;
  artifacts__checksum__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  artifacts__content_type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  artifacts__content_type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  artifacts__content_type__owner__id?: InputMaybe<Scalars["ID"]>;
  artifacts__content_type__source__id?: InputMaybe<Scalars["ID"]>;
  artifacts__content_type__value?: InputMaybe<Scalars["String"]>;
  artifacts__content_type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  artifacts__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  artifacts__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  artifacts__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  artifacts__name__owner__id?: InputMaybe<Scalars["ID"]>;
  artifacts__name__source__id?: InputMaybe<Scalars["ID"]>;
  artifacts__name__value?: InputMaybe<Scalars["String"]>;
  artifacts__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  artifacts__parameters__is_protected?: InputMaybe<Scalars["Boolean"]>;
  artifacts__parameters__is_visible?: InputMaybe<Scalars["Boolean"]>;
  artifacts__parameters__owner__id?: InputMaybe<Scalars["ID"]>;
  artifacts__parameters__source__id?: InputMaybe<Scalars["ID"]>;
  artifacts__parameters__value?: InputMaybe<Scalars["GenericScalar"]>;
  artifacts__parameters__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  artifacts__status__is_protected?: InputMaybe<Scalars["Boolean"]>;
  artifacts__status__is_visible?: InputMaybe<Scalars["Boolean"]>;
  artifacts__status__owner__id?: InputMaybe<Scalars["ID"]>;
  artifacts__status__source__id?: InputMaybe<Scalars["ID"]>;
  artifacts__status__value?: InputMaybe<Scalars["String"]>;
  artifacts__status__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  artifacts__storage_id__is_protected?: InputMaybe<Scalars["Boolean"]>;
  artifacts__storage_id__is_visible?: InputMaybe<Scalars["Boolean"]>;
  artifacts__storage_id__owner__id?: InputMaybe<Scalars["ID"]>;
  artifacts__storage_id__source__id?: InputMaybe<Scalars["ID"]>;
  artifacts__storage_id__value?: InputMaybe<Scalars["String"]>;
  artifacts__storage_id__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryCoreArtifactThreadArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  artifact_id__is_protected?: InputMaybe<Scalars["Boolean"]>;
  artifact_id__is_visible?: InputMaybe<Scalars["Boolean"]>;
  artifact_id__owner__id?: InputMaybe<Scalars["ID"]>;
  artifact_id__source__id?: InputMaybe<Scalars["ID"]>;
  artifact_id__value?: InputMaybe<Scalars["String"]>;
  artifact_id__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  change__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  change__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  change__description__owner__id?: InputMaybe<Scalars["ID"]>;
  change__description__source__id?: InputMaybe<Scalars["ID"]>;
  change__description__value?: InputMaybe<Scalars["String"]>;
  change__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  change__destination_branch__is_protected?: InputMaybe<Scalars["Boolean"]>;
  change__destination_branch__is_visible?: InputMaybe<Scalars["Boolean"]>;
  change__destination_branch__owner__id?: InputMaybe<Scalars["ID"]>;
  change__destination_branch__source__id?: InputMaybe<Scalars["ID"]>;
  change__destination_branch__value?: InputMaybe<Scalars["String"]>;
  change__destination_branch__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  change__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  change__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  change__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  change__name__owner__id?: InputMaybe<Scalars["ID"]>;
  change__name__source__id?: InputMaybe<Scalars["ID"]>;
  change__name__value?: InputMaybe<Scalars["String"]>;
  change__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  change__source_branch__is_protected?: InputMaybe<Scalars["Boolean"]>;
  change__source_branch__is_visible?: InputMaybe<Scalars["Boolean"]>;
  change__source_branch__owner__id?: InputMaybe<Scalars["ID"]>;
  change__source_branch__source__id?: InputMaybe<Scalars["ID"]>;
  change__source_branch__value?: InputMaybe<Scalars["String"]>;
  change__source_branch__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  change__state__is_protected?: InputMaybe<Scalars["Boolean"]>;
  change__state__is_visible?: InputMaybe<Scalars["Boolean"]>;
  change__state__owner__id?: InputMaybe<Scalars["ID"]>;
  change__state__source__id?: InputMaybe<Scalars["ID"]>;
  change__state__value?: InputMaybe<Scalars["String"]>;
  change__state__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  comments__created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  comments__created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  comments__created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  comments__created_at__source__id?: InputMaybe<Scalars["ID"]>;
  comments__created_at__value?: InputMaybe<Scalars["String"]>;
  comments__created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  comments__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  comments__text__is_protected?: InputMaybe<Scalars["Boolean"]>;
  comments__text__is_visible?: InputMaybe<Scalars["Boolean"]>;
  comments__text__owner__id?: InputMaybe<Scalars["ID"]>;
  comments__text__source__id?: InputMaybe<Scalars["ID"]>;
  comments__text__value?: InputMaybe<Scalars["String"]>;
  comments__text__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  created_at__source__id?: InputMaybe<Scalars["ID"]>;
  created_at__value?: InputMaybe<Scalars["String"]>;
  created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__description__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__description__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__description__value?: InputMaybe<Scalars["String"]>;
  created_by__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  created_by__label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__label__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__label__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__label__value?: InputMaybe<Scalars["String"]>;
  created_by__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__name__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__name__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__name__value?: InputMaybe<Scalars["String"]>;
  created_by__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__password__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__password__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__password__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__password__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__password__value?: InputMaybe<Scalars["String"]>;
  created_by__password__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__role__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__role__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__role__value?: InputMaybe<Scalars["String"]>;
  created_by__role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__type__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__type__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__type__value?: InputMaybe<Scalars["String"]>;
  created_by__type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  line_number__is_protected?: InputMaybe<Scalars["Boolean"]>;
  line_number__is_visible?: InputMaybe<Scalars["Boolean"]>;
  line_number__owner__id?: InputMaybe<Scalars["ID"]>;
  line_number__source__id?: InputMaybe<Scalars["ID"]>;
  line_number__value?: InputMaybe<Scalars["Int"]>;
  line_number__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  resolved__is_protected?: InputMaybe<Scalars["Boolean"]>;
  resolved__is_visible?: InputMaybe<Scalars["Boolean"]>;
  resolved__owner__id?: InputMaybe<Scalars["ID"]>;
  resolved__source__id?: InputMaybe<Scalars["ID"]>;
  resolved__value?: InputMaybe<Scalars["Boolean"]>;
  resolved__values?: InputMaybe<Array<InputMaybe<Scalars["Boolean"]>>>;
  storage_id__is_protected?: InputMaybe<Scalars["Boolean"]>;
  storage_id__is_visible?: InputMaybe<Scalars["Boolean"]>;
  storage_id__owner__id?: InputMaybe<Scalars["ID"]>;
  storage_id__source__id?: InputMaybe<Scalars["ID"]>;
  storage_id__value?: InputMaybe<Scalars["String"]>;
  storage_id__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryCoreArtifactValidatorArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__conclusion__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__conclusion__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__conclusion__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__conclusion__source__id?: InputMaybe<Scalars["ID"]>;
  checks__conclusion__value?: InputMaybe<Scalars["String"]>;
  checks__conclusion__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__created_at__source__id?: InputMaybe<Scalars["ID"]>;
  checks__created_at__value?: InputMaybe<Scalars["String"]>;
  checks__created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  checks__kind__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__kind__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__kind__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__kind__source__id?: InputMaybe<Scalars["ID"]>;
  checks__kind__value?: InputMaybe<Scalars["String"]>;
  checks__kind__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__label__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__label__source__id?: InputMaybe<Scalars["ID"]>;
  checks__label__value?: InputMaybe<Scalars["String"]>;
  checks__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__message__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__message__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__message__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__message__source__id?: InputMaybe<Scalars["ID"]>;
  checks__message__value?: InputMaybe<Scalars["String"]>;
  checks__message__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__name__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__name__source__id?: InputMaybe<Scalars["ID"]>;
  checks__name__value?: InputMaybe<Scalars["String"]>;
  checks__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__origin__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__origin__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__origin__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__origin__source__id?: InputMaybe<Scalars["ID"]>;
  checks__origin__value?: InputMaybe<Scalars["String"]>;
  checks__origin__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__severity__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__severity__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__severity__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__severity__source__id?: InputMaybe<Scalars["ID"]>;
  checks__severity__value?: InputMaybe<Scalars["String"]>;
  checks__severity__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  completed_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  completed_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  completed_at__owner__id?: InputMaybe<Scalars["ID"]>;
  completed_at__source__id?: InputMaybe<Scalars["ID"]>;
  completed_at__value?: InputMaybe<Scalars["String"]>;
  completed_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  conclusion__is_protected?: InputMaybe<Scalars["Boolean"]>;
  conclusion__is_visible?: InputMaybe<Scalars["Boolean"]>;
  conclusion__owner__id?: InputMaybe<Scalars["ID"]>;
  conclusion__source__id?: InputMaybe<Scalars["ID"]>;
  conclusion__value?: InputMaybe<Scalars["String"]>;
  conclusion__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  definition__artifact_name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  definition__artifact_name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  definition__artifact_name__owner__id?: InputMaybe<Scalars["ID"]>;
  definition__artifact_name__source__id?: InputMaybe<Scalars["ID"]>;
  definition__artifact_name__value?: InputMaybe<Scalars["String"]>;
  definition__artifact_name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  definition__content_type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  definition__content_type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  definition__content_type__owner__id?: InputMaybe<Scalars["ID"]>;
  definition__content_type__source__id?: InputMaybe<Scalars["ID"]>;
  definition__content_type__value?: InputMaybe<Scalars["String"]>;
  definition__content_type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  definition__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  definition__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  definition__description__owner__id?: InputMaybe<Scalars["ID"]>;
  definition__description__source__id?: InputMaybe<Scalars["ID"]>;
  definition__description__value?: InputMaybe<Scalars["String"]>;
  definition__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  definition__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  definition__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  definition__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  definition__name__owner__id?: InputMaybe<Scalars["ID"]>;
  definition__name__source__id?: InputMaybe<Scalars["ID"]>;
  definition__name__value?: InputMaybe<Scalars["String"]>;
  definition__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  definition__parameters__is_protected?: InputMaybe<Scalars["Boolean"]>;
  definition__parameters__is_visible?: InputMaybe<Scalars["Boolean"]>;
  definition__parameters__owner__id?: InputMaybe<Scalars["ID"]>;
  definition__parameters__source__id?: InputMaybe<Scalars["ID"]>;
  definition__parameters__value?: InputMaybe<Scalars["GenericScalar"]>;
  definition__parameters__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__description__owner__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__description__source__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__description__value?: InputMaybe<Scalars["String"]>;
  proposed_change__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  proposed_change__destination_branch__is_protected?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__destination_branch__is_visible?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__destination_branch__owner__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__destination_branch__source__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__destination_branch__value?: InputMaybe<Scalars["String"]>;
  proposed_change__destination_branch__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  proposed_change__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  proposed_change__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__name__owner__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__name__source__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__name__value?: InputMaybe<Scalars["String"]>;
  proposed_change__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  proposed_change__source_branch__is_protected?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__source_branch__is_visible?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__source_branch__owner__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__source_branch__source__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__source_branch__value?: InputMaybe<Scalars["String"]>;
  proposed_change__source_branch__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  proposed_change__state__is_protected?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__state__is_visible?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__state__owner__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__state__source__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__state__value?: InputMaybe<Scalars["String"]>;
  proposed_change__state__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  started_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  started_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  started_at__owner__id?: InputMaybe<Scalars["ID"]>;
  started_at__source__id?: InputMaybe<Scalars["ID"]>;
  started_at__value?: InputMaybe<Scalars["String"]>;
  started_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  state__is_protected?: InputMaybe<Scalars["Boolean"]>;
  state__is_visible?: InputMaybe<Scalars["Boolean"]>;
  state__owner__id?: InputMaybe<Scalars["ID"]>;
  state__source__id?: InputMaybe<Scalars["ID"]>;
  state__value?: InputMaybe<Scalars["String"]>;
  state__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryCoreChangeCommentArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  change__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  change__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  change__description__owner__id?: InputMaybe<Scalars["ID"]>;
  change__description__source__id?: InputMaybe<Scalars["ID"]>;
  change__description__value?: InputMaybe<Scalars["String"]>;
  change__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  change__destination_branch__is_protected?: InputMaybe<Scalars["Boolean"]>;
  change__destination_branch__is_visible?: InputMaybe<Scalars["Boolean"]>;
  change__destination_branch__owner__id?: InputMaybe<Scalars["ID"]>;
  change__destination_branch__source__id?: InputMaybe<Scalars["ID"]>;
  change__destination_branch__value?: InputMaybe<Scalars["String"]>;
  change__destination_branch__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  change__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  change__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  change__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  change__name__owner__id?: InputMaybe<Scalars["ID"]>;
  change__name__source__id?: InputMaybe<Scalars["ID"]>;
  change__name__value?: InputMaybe<Scalars["String"]>;
  change__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  change__source_branch__is_protected?: InputMaybe<Scalars["Boolean"]>;
  change__source_branch__is_visible?: InputMaybe<Scalars["Boolean"]>;
  change__source_branch__owner__id?: InputMaybe<Scalars["ID"]>;
  change__source_branch__source__id?: InputMaybe<Scalars["ID"]>;
  change__source_branch__value?: InputMaybe<Scalars["String"]>;
  change__source_branch__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  change__state__is_protected?: InputMaybe<Scalars["Boolean"]>;
  change__state__is_visible?: InputMaybe<Scalars["Boolean"]>;
  change__state__owner__id?: InputMaybe<Scalars["ID"]>;
  change__state__source__id?: InputMaybe<Scalars["ID"]>;
  change__state__value?: InputMaybe<Scalars["String"]>;
  change__state__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  created_at__source__id?: InputMaybe<Scalars["ID"]>;
  created_at__value?: InputMaybe<Scalars["String"]>;
  created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__description__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__description__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__description__value?: InputMaybe<Scalars["String"]>;
  created_by__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  created_by__label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__label__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__label__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__label__value?: InputMaybe<Scalars["String"]>;
  created_by__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__name__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__name__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__name__value?: InputMaybe<Scalars["String"]>;
  created_by__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__password__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__password__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__password__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__password__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__password__value?: InputMaybe<Scalars["String"]>;
  created_by__password__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__role__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__role__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__role__value?: InputMaybe<Scalars["String"]>;
  created_by__role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__type__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__type__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__type__value?: InputMaybe<Scalars["String"]>;
  created_by__type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  text__is_protected?: InputMaybe<Scalars["Boolean"]>;
  text__is_visible?: InputMaybe<Scalars["Boolean"]>;
  text__owner__id?: InputMaybe<Scalars["ID"]>;
  text__source__id?: InputMaybe<Scalars["ID"]>;
  text__value?: InputMaybe<Scalars["String"]>;
  text__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryCoreChangeThreadArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  change__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  change__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  change__description__owner__id?: InputMaybe<Scalars["ID"]>;
  change__description__source__id?: InputMaybe<Scalars["ID"]>;
  change__description__value?: InputMaybe<Scalars["String"]>;
  change__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  change__destination_branch__is_protected?: InputMaybe<Scalars["Boolean"]>;
  change__destination_branch__is_visible?: InputMaybe<Scalars["Boolean"]>;
  change__destination_branch__owner__id?: InputMaybe<Scalars["ID"]>;
  change__destination_branch__source__id?: InputMaybe<Scalars["ID"]>;
  change__destination_branch__value?: InputMaybe<Scalars["String"]>;
  change__destination_branch__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  change__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  change__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  change__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  change__name__owner__id?: InputMaybe<Scalars["ID"]>;
  change__name__source__id?: InputMaybe<Scalars["ID"]>;
  change__name__value?: InputMaybe<Scalars["String"]>;
  change__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  change__source_branch__is_protected?: InputMaybe<Scalars["Boolean"]>;
  change__source_branch__is_visible?: InputMaybe<Scalars["Boolean"]>;
  change__source_branch__owner__id?: InputMaybe<Scalars["ID"]>;
  change__source_branch__source__id?: InputMaybe<Scalars["ID"]>;
  change__source_branch__value?: InputMaybe<Scalars["String"]>;
  change__source_branch__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  change__state__is_protected?: InputMaybe<Scalars["Boolean"]>;
  change__state__is_visible?: InputMaybe<Scalars["Boolean"]>;
  change__state__owner__id?: InputMaybe<Scalars["ID"]>;
  change__state__source__id?: InputMaybe<Scalars["ID"]>;
  change__state__value?: InputMaybe<Scalars["String"]>;
  change__state__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  comments__created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  comments__created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  comments__created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  comments__created_at__source__id?: InputMaybe<Scalars["ID"]>;
  comments__created_at__value?: InputMaybe<Scalars["String"]>;
  comments__created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  comments__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  comments__text__is_protected?: InputMaybe<Scalars["Boolean"]>;
  comments__text__is_visible?: InputMaybe<Scalars["Boolean"]>;
  comments__text__owner__id?: InputMaybe<Scalars["ID"]>;
  comments__text__source__id?: InputMaybe<Scalars["ID"]>;
  comments__text__value?: InputMaybe<Scalars["String"]>;
  comments__text__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  created_at__source__id?: InputMaybe<Scalars["ID"]>;
  created_at__value?: InputMaybe<Scalars["String"]>;
  created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__description__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__description__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__description__value?: InputMaybe<Scalars["String"]>;
  created_by__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  created_by__label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__label__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__label__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__label__value?: InputMaybe<Scalars["String"]>;
  created_by__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__name__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__name__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__name__value?: InputMaybe<Scalars["String"]>;
  created_by__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__password__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__password__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__password__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__password__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__password__value?: InputMaybe<Scalars["String"]>;
  created_by__password__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__role__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__role__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__role__value?: InputMaybe<Scalars["String"]>;
  created_by__role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__type__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__type__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__type__value?: InputMaybe<Scalars["String"]>;
  created_by__type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  resolved__is_protected?: InputMaybe<Scalars["Boolean"]>;
  resolved__is_visible?: InputMaybe<Scalars["Boolean"]>;
  resolved__owner__id?: InputMaybe<Scalars["ID"]>;
  resolved__source__id?: InputMaybe<Scalars["ID"]>;
  resolved__value?: InputMaybe<Scalars["Boolean"]>;
  resolved__values?: InputMaybe<Array<InputMaybe<Scalars["Boolean"]>>>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryCoreCheckArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  conclusion__is_protected?: InputMaybe<Scalars["Boolean"]>;
  conclusion__is_visible?: InputMaybe<Scalars["Boolean"]>;
  conclusion__owner__id?: InputMaybe<Scalars["ID"]>;
  conclusion__source__id?: InputMaybe<Scalars["ID"]>;
  conclusion__value?: InputMaybe<Scalars["String"]>;
  conclusion__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  created_at__source__id?: InputMaybe<Scalars["ID"]>;
  created_at__value?: InputMaybe<Scalars["String"]>;
  created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  kind__is_protected?: InputMaybe<Scalars["Boolean"]>;
  kind__is_visible?: InputMaybe<Scalars["Boolean"]>;
  kind__owner__id?: InputMaybe<Scalars["ID"]>;
  kind__source__id?: InputMaybe<Scalars["ID"]>;
  kind__value?: InputMaybe<Scalars["String"]>;
  kind__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  message__is_protected?: InputMaybe<Scalars["Boolean"]>;
  message__is_visible?: InputMaybe<Scalars["Boolean"]>;
  message__owner__id?: InputMaybe<Scalars["ID"]>;
  message__source__id?: InputMaybe<Scalars["ID"]>;
  message__value?: InputMaybe<Scalars["String"]>;
  message__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  origin__is_protected?: InputMaybe<Scalars["Boolean"]>;
  origin__is_visible?: InputMaybe<Scalars["Boolean"]>;
  origin__owner__id?: InputMaybe<Scalars["ID"]>;
  origin__source__id?: InputMaybe<Scalars["ID"]>;
  origin__value?: InputMaybe<Scalars["String"]>;
  origin__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  severity__is_protected?: InputMaybe<Scalars["Boolean"]>;
  severity__is_visible?: InputMaybe<Scalars["Boolean"]>;
  severity__owner__id?: InputMaybe<Scalars["ID"]>;
  severity__source__id?: InputMaybe<Scalars["ID"]>;
  severity__value?: InputMaybe<Scalars["String"]>;
  severity__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  validator__completed_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  validator__completed_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  validator__completed_at__owner__id?: InputMaybe<Scalars["ID"]>;
  validator__completed_at__source__id?: InputMaybe<Scalars["ID"]>;
  validator__completed_at__value?: InputMaybe<Scalars["String"]>;
  validator__completed_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  validator__conclusion__is_protected?: InputMaybe<Scalars["Boolean"]>;
  validator__conclusion__is_visible?: InputMaybe<Scalars["Boolean"]>;
  validator__conclusion__owner__id?: InputMaybe<Scalars["ID"]>;
  validator__conclusion__source__id?: InputMaybe<Scalars["ID"]>;
  validator__conclusion__value?: InputMaybe<Scalars["String"]>;
  validator__conclusion__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  validator__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  validator__label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  validator__label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  validator__label__owner__id?: InputMaybe<Scalars["ID"]>;
  validator__label__source__id?: InputMaybe<Scalars["ID"]>;
  validator__label__value?: InputMaybe<Scalars["String"]>;
  validator__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  validator__started_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  validator__started_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  validator__started_at__owner__id?: InputMaybe<Scalars["ID"]>;
  validator__started_at__source__id?: InputMaybe<Scalars["ID"]>;
  validator__started_at__value?: InputMaybe<Scalars["String"]>;
  validator__started_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  validator__state__is_protected?: InputMaybe<Scalars["Boolean"]>;
  validator__state__is_visible?: InputMaybe<Scalars["Boolean"]>;
  validator__state__owner__id?: InputMaybe<Scalars["ID"]>;
  validator__state__source__id?: InputMaybe<Scalars["ID"]>;
  validator__state__value?: InputMaybe<Scalars["String"]>;
  validator__state__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryCoreCheckDefinitionArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  class_name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  class_name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  class_name__owner__id?: InputMaybe<Scalars["ID"]>;
  class_name__source__id?: InputMaybe<Scalars["ID"]>;
  class_name__value?: InputMaybe<Scalars["String"]>;
  class_name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  file_path__is_protected?: InputMaybe<Scalars["Boolean"]>;
  file_path__is_visible?: InputMaybe<Scalars["Boolean"]>;
  file_path__owner__id?: InputMaybe<Scalars["ID"]>;
  file_path__source__id?: InputMaybe<Scalars["ID"]>;
  file_path__value?: InputMaybe<Scalars["String"]>;
  file_path__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  parameters__is_protected?: InputMaybe<Scalars["Boolean"]>;
  parameters__is_visible?: InputMaybe<Scalars["Boolean"]>;
  parameters__owner__id?: InputMaybe<Scalars["ID"]>;
  parameters__source__id?: InputMaybe<Scalars["ID"]>;
  parameters__value?: InputMaybe<Scalars["GenericScalar"]>;
  parameters__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  query__depth__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__depth__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__depth__owner__id?: InputMaybe<Scalars["ID"]>;
  query__depth__source__id?: InputMaybe<Scalars["ID"]>;
  query__depth__value?: InputMaybe<Scalars["Int"]>;
  query__depth__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  query__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__description__owner__id?: InputMaybe<Scalars["ID"]>;
  query__description__source__id?: InputMaybe<Scalars["ID"]>;
  query__description__value?: InputMaybe<Scalars["String"]>;
  query__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  query__height__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__height__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__height__owner__id?: InputMaybe<Scalars["ID"]>;
  query__height__source__id?: InputMaybe<Scalars["ID"]>;
  query__height__value?: InputMaybe<Scalars["Int"]>;
  query__height__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  query__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  query__models__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__models__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__models__owner__id?: InputMaybe<Scalars["ID"]>;
  query__models__source__id?: InputMaybe<Scalars["ID"]>;
  query__models__value?: InputMaybe<Scalars["GenericScalar"]>;
  query__models__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  query__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__name__owner__id?: InputMaybe<Scalars["ID"]>;
  query__name__source__id?: InputMaybe<Scalars["ID"]>;
  query__name__value?: InputMaybe<Scalars["String"]>;
  query__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  query__operations__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__operations__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__operations__owner__id?: InputMaybe<Scalars["ID"]>;
  query__operations__source__id?: InputMaybe<Scalars["ID"]>;
  query__operations__value?: InputMaybe<Scalars["GenericScalar"]>;
  query__operations__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  query__query__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__query__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__query__owner__id?: InputMaybe<Scalars["ID"]>;
  query__query__source__id?: InputMaybe<Scalars["ID"]>;
  query__query__value?: InputMaybe<Scalars["String"]>;
  query__query__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  query__variables__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__variables__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__variables__owner__id?: InputMaybe<Scalars["ID"]>;
  query__variables__source__id?: InputMaybe<Scalars["ID"]>;
  query__variables__value?: InputMaybe<Scalars["GenericScalar"]>;
  query__variables__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  repository__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__description__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__description__source__id?: InputMaybe<Scalars["ID"]>;
  repository__description__value?: InputMaybe<Scalars["String"]>;
  repository__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  repository__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  repository__location__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__location__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__location__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__location__source__id?: InputMaybe<Scalars["ID"]>;
  repository__location__value?: InputMaybe<Scalars["String"]>;
  repository__location__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  repository__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__name__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__name__source__id?: InputMaybe<Scalars["ID"]>;
  repository__name__value?: InputMaybe<Scalars["String"]>;
  repository__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  repository__password__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__password__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__password__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__password__source__id?: InputMaybe<Scalars["ID"]>;
  repository__password__value?: InputMaybe<Scalars["String"]>;
  repository__password__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  repository__username__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__username__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__username__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__username__source__id?: InputMaybe<Scalars["ID"]>;
  repository__username__value?: InputMaybe<Scalars["String"]>;
  repository__username__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  tags__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  tags__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  tags__description__owner__id?: InputMaybe<Scalars["ID"]>;
  tags__description__source__id?: InputMaybe<Scalars["ID"]>;
  tags__description__value?: InputMaybe<Scalars["String"]>;
  tags__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  tags__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  tags__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  tags__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  tags__name__owner__id?: InputMaybe<Scalars["ID"]>;
  tags__name__source__id?: InputMaybe<Scalars["ID"]>;
  tags__name__value?: InputMaybe<Scalars["String"]>;
  tags__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  targets__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  targets__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  targets__description__owner__id?: InputMaybe<Scalars["ID"]>;
  targets__description__source__id?: InputMaybe<Scalars["ID"]>;
  targets__description__value?: InputMaybe<Scalars["String"]>;
  targets__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  targets__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  targets__label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  targets__label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  targets__label__owner__id?: InputMaybe<Scalars["ID"]>;
  targets__label__source__id?: InputMaybe<Scalars["ID"]>;
  targets__label__value?: InputMaybe<Scalars["String"]>;
  targets__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  targets__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  targets__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  targets__name__owner__id?: InputMaybe<Scalars["ID"]>;
  targets__name__source__id?: InputMaybe<Scalars["ID"]>;
  targets__name__value?: InputMaybe<Scalars["String"]>;
  targets__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  timeout__is_protected?: InputMaybe<Scalars["Boolean"]>;
  timeout__is_visible?: InputMaybe<Scalars["Boolean"]>;
  timeout__owner__id?: InputMaybe<Scalars["ID"]>;
  timeout__source__id?: InputMaybe<Scalars["ID"]>;
  timeout__value?: InputMaybe<Scalars["Int"]>;
  timeout__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
};

export type QueryCoreCommentArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  created_at__source__id?: InputMaybe<Scalars["ID"]>;
  created_at__value?: InputMaybe<Scalars["String"]>;
  created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__description__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__description__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__description__value?: InputMaybe<Scalars["String"]>;
  created_by__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  created_by__label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__label__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__label__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__label__value?: InputMaybe<Scalars["String"]>;
  created_by__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__name__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__name__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__name__value?: InputMaybe<Scalars["String"]>;
  created_by__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__password__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__password__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__password__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__password__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__password__value?: InputMaybe<Scalars["String"]>;
  created_by__password__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__role__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__role__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__role__value?: InputMaybe<Scalars["String"]>;
  created_by__role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__type__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__type__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__type__value?: InputMaybe<Scalars["String"]>;
  created_by__type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  text__is_protected?: InputMaybe<Scalars["Boolean"]>;
  text__is_visible?: InputMaybe<Scalars["Boolean"]>;
  text__owner__id?: InputMaybe<Scalars["ID"]>;
  text__source__id?: InputMaybe<Scalars["ID"]>;
  text__value?: InputMaybe<Scalars["String"]>;
  text__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryCoreCustomWebhookArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  transformation__class_name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  transformation__class_name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  transformation__class_name__owner__id?: InputMaybe<Scalars["ID"]>;
  transformation__class_name__source__id?: InputMaybe<Scalars["ID"]>;
  transformation__class_name__value?: InputMaybe<Scalars["String"]>;
  transformation__class_name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  transformation__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  transformation__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  transformation__description__owner__id?: InputMaybe<Scalars["ID"]>;
  transformation__description__source__id?: InputMaybe<Scalars["ID"]>;
  transformation__description__value?: InputMaybe<Scalars["String"]>;
  transformation__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  transformation__file_path__is_protected?: InputMaybe<Scalars["Boolean"]>;
  transformation__file_path__is_visible?: InputMaybe<Scalars["Boolean"]>;
  transformation__file_path__owner__id?: InputMaybe<Scalars["ID"]>;
  transformation__file_path__source__id?: InputMaybe<Scalars["ID"]>;
  transformation__file_path__value?: InputMaybe<Scalars["String"]>;
  transformation__file_path__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  transformation__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  transformation__label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  transformation__label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  transformation__label__owner__id?: InputMaybe<Scalars["ID"]>;
  transformation__label__source__id?: InputMaybe<Scalars["ID"]>;
  transformation__label__value?: InputMaybe<Scalars["String"]>;
  transformation__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  transformation__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  transformation__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  transformation__name__owner__id?: InputMaybe<Scalars["ID"]>;
  transformation__name__source__id?: InputMaybe<Scalars["ID"]>;
  transformation__name__value?: InputMaybe<Scalars["String"]>;
  transformation__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  transformation__timeout__is_protected?: InputMaybe<Scalars["Boolean"]>;
  transformation__timeout__is_visible?: InputMaybe<Scalars["Boolean"]>;
  transformation__timeout__owner__id?: InputMaybe<Scalars["ID"]>;
  transformation__timeout__source__id?: InputMaybe<Scalars["ID"]>;
  transformation__timeout__value?: InputMaybe<Scalars["Int"]>;
  transformation__timeout__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  url__is_protected?: InputMaybe<Scalars["Boolean"]>;
  url__is_visible?: InputMaybe<Scalars["Boolean"]>;
  url__owner__id?: InputMaybe<Scalars["ID"]>;
  url__source__id?: InputMaybe<Scalars["ID"]>;
  url__value?: InputMaybe<Scalars["String"]>;
  url__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  validate_certificates__is_protected?: InputMaybe<Scalars["Boolean"]>;
  validate_certificates__is_visible?: InputMaybe<Scalars["Boolean"]>;
  validate_certificates__owner__id?: InputMaybe<Scalars["ID"]>;
  validate_certificates__source__id?: InputMaybe<Scalars["ID"]>;
  validate_certificates__value?: InputMaybe<Scalars["Boolean"]>;
  validate_certificates__values?: InputMaybe<Array<InputMaybe<Scalars["Boolean"]>>>;
};

export type QueryCoreDataCheckArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  conclusion__is_protected?: InputMaybe<Scalars["Boolean"]>;
  conclusion__is_visible?: InputMaybe<Scalars["Boolean"]>;
  conclusion__owner__id?: InputMaybe<Scalars["ID"]>;
  conclusion__source__id?: InputMaybe<Scalars["ID"]>;
  conclusion__value?: InputMaybe<Scalars["String"]>;
  conclusion__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  conflicts__is_protected?: InputMaybe<Scalars["Boolean"]>;
  conflicts__is_visible?: InputMaybe<Scalars["Boolean"]>;
  conflicts__owner__id?: InputMaybe<Scalars["ID"]>;
  conflicts__source__id?: InputMaybe<Scalars["ID"]>;
  conflicts__value?: InputMaybe<Scalars["GenericScalar"]>;
  conflicts__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  created_at__source__id?: InputMaybe<Scalars["ID"]>;
  created_at__value?: InputMaybe<Scalars["String"]>;
  created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  keep_branch__is_protected?: InputMaybe<Scalars["Boolean"]>;
  keep_branch__is_visible?: InputMaybe<Scalars["Boolean"]>;
  keep_branch__owner__id?: InputMaybe<Scalars["ID"]>;
  keep_branch__source__id?: InputMaybe<Scalars["ID"]>;
  keep_branch__value?: InputMaybe<Scalars["String"]>;
  keep_branch__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  kind__is_protected?: InputMaybe<Scalars["Boolean"]>;
  kind__is_visible?: InputMaybe<Scalars["Boolean"]>;
  kind__owner__id?: InputMaybe<Scalars["ID"]>;
  kind__source__id?: InputMaybe<Scalars["ID"]>;
  kind__value?: InputMaybe<Scalars["String"]>;
  kind__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  message__is_protected?: InputMaybe<Scalars["Boolean"]>;
  message__is_visible?: InputMaybe<Scalars["Boolean"]>;
  message__owner__id?: InputMaybe<Scalars["ID"]>;
  message__source__id?: InputMaybe<Scalars["ID"]>;
  message__value?: InputMaybe<Scalars["String"]>;
  message__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  origin__is_protected?: InputMaybe<Scalars["Boolean"]>;
  origin__is_visible?: InputMaybe<Scalars["Boolean"]>;
  origin__owner__id?: InputMaybe<Scalars["ID"]>;
  origin__source__id?: InputMaybe<Scalars["ID"]>;
  origin__value?: InputMaybe<Scalars["String"]>;
  origin__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  severity__is_protected?: InputMaybe<Scalars["Boolean"]>;
  severity__is_visible?: InputMaybe<Scalars["Boolean"]>;
  severity__owner__id?: InputMaybe<Scalars["ID"]>;
  severity__source__id?: InputMaybe<Scalars["ID"]>;
  severity__value?: InputMaybe<Scalars["String"]>;
  severity__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  validator__completed_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  validator__completed_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  validator__completed_at__owner__id?: InputMaybe<Scalars["ID"]>;
  validator__completed_at__source__id?: InputMaybe<Scalars["ID"]>;
  validator__completed_at__value?: InputMaybe<Scalars["String"]>;
  validator__completed_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  validator__conclusion__is_protected?: InputMaybe<Scalars["Boolean"]>;
  validator__conclusion__is_visible?: InputMaybe<Scalars["Boolean"]>;
  validator__conclusion__owner__id?: InputMaybe<Scalars["ID"]>;
  validator__conclusion__source__id?: InputMaybe<Scalars["ID"]>;
  validator__conclusion__value?: InputMaybe<Scalars["String"]>;
  validator__conclusion__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  validator__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  validator__label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  validator__label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  validator__label__owner__id?: InputMaybe<Scalars["ID"]>;
  validator__label__source__id?: InputMaybe<Scalars["ID"]>;
  validator__label__value?: InputMaybe<Scalars["String"]>;
  validator__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  validator__started_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  validator__started_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  validator__started_at__owner__id?: InputMaybe<Scalars["ID"]>;
  validator__started_at__source__id?: InputMaybe<Scalars["ID"]>;
  validator__started_at__value?: InputMaybe<Scalars["String"]>;
  validator__started_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  validator__state__is_protected?: InputMaybe<Scalars["Boolean"]>;
  validator__state__is_visible?: InputMaybe<Scalars["Boolean"]>;
  validator__state__owner__id?: InputMaybe<Scalars["ID"]>;
  validator__state__source__id?: InputMaybe<Scalars["ID"]>;
  validator__state__value?: InputMaybe<Scalars["String"]>;
  validator__state__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryCoreDataValidatorArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__conclusion__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__conclusion__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__conclusion__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__conclusion__source__id?: InputMaybe<Scalars["ID"]>;
  checks__conclusion__value?: InputMaybe<Scalars["String"]>;
  checks__conclusion__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__created_at__source__id?: InputMaybe<Scalars["ID"]>;
  checks__created_at__value?: InputMaybe<Scalars["String"]>;
  checks__created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  checks__kind__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__kind__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__kind__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__kind__source__id?: InputMaybe<Scalars["ID"]>;
  checks__kind__value?: InputMaybe<Scalars["String"]>;
  checks__kind__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__label__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__label__source__id?: InputMaybe<Scalars["ID"]>;
  checks__label__value?: InputMaybe<Scalars["String"]>;
  checks__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__message__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__message__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__message__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__message__source__id?: InputMaybe<Scalars["ID"]>;
  checks__message__value?: InputMaybe<Scalars["String"]>;
  checks__message__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__name__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__name__source__id?: InputMaybe<Scalars["ID"]>;
  checks__name__value?: InputMaybe<Scalars["String"]>;
  checks__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__origin__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__origin__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__origin__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__origin__source__id?: InputMaybe<Scalars["ID"]>;
  checks__origin__value?: InputMaybe<Scalars["String"]>;
  checks__origin__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__severity__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__severity__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__severity__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__severity__source__id?: InputMaybe<Scalars["ID"]>;
  checks__severity__value?: InputMaybe<Scalars["String"]>;
  checks__severity__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  completed_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  completed_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  completed_at__owner__id?: InputMaybe<Scalars["ID"]>;
  completed_at__source__id?: InputMaybe<Scalars["ID"]>;
  completed_at__value?: InputMaybe<Scalars["String"]>;
  completed_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  conclusion__is_protected?: InputMaybe<Scalars["Boolean"]>;
  conclusion__is_visible?: InputMaybe<Scalars["Boolean"]>;
  conclusion__owner__id?: InputMaybe<Scalars["ID"]>;
  conclusion__source__id?: InputMaybe<Scalars["ID"]>;
  conclusion__value?: InputMaybe<Scalars["String"]>;
  conclusion__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__description__owner__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__description__source__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__description__value?: InputMaybe<Scalars["String"]>;
  proposed_change__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  proposed_change__destination_branch__is_protected?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__destination_branch__is_visible?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__destination_branch__owner__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__destination_branch__source__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__destination_branch__value?: InputMaybe<Scalars["String"]>;
  proposed_change__destination_branch__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  proposed_change__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  proposed_change__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__name__owner__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__name__source__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__name__value?: InputMaybe<Scalars["String"]>;
  proposed_change__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  proposed_change__source_branch__is_protected?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__source_branch__is_visible?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__source_branch__owner__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__source_branch__source__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__source_branch__value?: InputMaybe<Scalars["String"]>;
  proposed_change__source_branch__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  proposed_change__state__is_protected?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__state__is_visible?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__state__owner__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__state__source__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__state__value?: InputMaybe<Scalars["String"]>;
  proposed_change__state__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  started_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  started_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  started_at__owner__id?: InputMaybe<Scalars["ID"]>;
  started_at__source__id?: InputMaybe<Scalars["ID"]>;
  started_at__value?: InputMaybe<Scalars["String"]>;
  started_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  state__is_protected?: InputMaybe<Scalars["Boolean"]>;
  state__is_visible?: InputMaybe<Scalars["Boolean"]>;
  state__owner__id?: InputMaybe<Scalars["ID"]>;
  state__source__id?: InputMaybe<Scalars["ID"]>;
  state__value?: InputMaybe<Scalars["String"]>;
  state__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryCoreFileCheckArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  commit__is_protected?: InputMaybe<Scalars["Boolean"]>;
  commit__is_visible?: InputMaybe<Scalars["Boolean"]>;
  commit__owner__id?: InputMaybe<Scalars["ID"]>;
  commit__source__id?: InputMaybe<Scalars["ID"]>;
  commit__value?: InputMaybe<Scalars["String"]>;
  commit__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  conclusion__is_protected?: InputMaybe<Scalars["Boolean"]>;
  conclusion__is_visible?: InputMaybe<Scalars["Boolean"]>;
  conclusion__owner__id?: InputMaybe<Scalars["ID"]>;
  conclusion__source__id?: InputMaybe<Scalars["ID"]>;
  conclusion__value?: InputMaybe<Scalars["String"]>;
  conclusion__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  created_at__source__id?: InputMaybe<Scalars["ID"]>;
  created_at__value?: InputMaybe<Scalars["String"]>;
  created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  files__is_protected?: InputMaybe<Scalars["Boolean"]>;
  files__is_visible?: InputMaybe<Scalars["Boolean"]>;
  files__owner__id?: InputMaybe<Scalars["ID"]>;
  files__source__id?: InputMaybe<Scalars["ID"]>;
  files__value?: InputMaybe<Scalars["GenericScalar"]>;
  files__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  kind__is_protected?: InputMaybe<Scalars["Boolean"]>;
  kind__is_visible?: InputMaybe<Scalars["Boolean"]>;
  kind__owner__id?: InputMaybe<Scalars["ID"]>;
  kind__source__id?: InputMaybe<Scalars["ID"]>;
  kind__value?: InputMaybe<Scalars["String"]>;
  kind__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  message__is_protected?: InputMaybe<Scalars["Boolean"]>;
  message__is_visible?: InputMaybe<Scalars["Boolean"]>;
  message__owner__id?: InputMaybe<Scalars["ID"]>;
  message__source__id?: InputMaybe<Scalars["ID"]>;
  message__value?: InputMaybe<Scalars["String"]>;
  message__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  origin__is_protected?: InputMaybe<Scalars["Boolean"]>;
  origin__is_visible?: InputMaybe<Scalars["Boolean"]>;
  origin__owner__id?: InputMaybe<Scalars["ID"]>;
  origin__source__id?: InputMaybe<Scalars["ID"]>;
  origin__value?: InputMaybe<Scalars["String"]>;
  origin__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  severity__is_protected?: InputMaybe<Scalars["Boolean"]>;
  severity__is_visible?: InputMaybe<Scalars["Boolean"]>;
  severity__owner__id?: InputMaybe<Scalars["ID"]>;
  severity__source__id?: InputMaybe<Scalars["ID"]>;
  severity__value?: InputMaybe<Scalars["String"]>;
  severity__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  validator__completed_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  validator__completed_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  validator__completed_at__owner__id?: InputMaybe<Scalars["ID"]>;
  validator__completed_at__source__id?: InputMaybe<Scalars["ID"]>;
  validator__completed_at__value?: InputMaybe<Scalars["String"]>;
  validator__completed_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  validator__conclusion__is_protected?: InputMaybe<Scalars["Boolean"]>;
  validator__conclusion__is_visible?: InputMaybe<Scalars["Boolean"]>;
  validator__conclusion__owner__id?: InputMaybe<Scalars["ID"]>;
  validator__conclusion__source__id?: InputMaybe<Scalars["ID"]>;
  validator__conclusion__value?: InputMaybe<Scalars["String"]>;
  validator__conclusion__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  validator__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  validator__label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  validator__label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  validator__label__owner__id?: InputMaybe<Scalars["ID"]>;
  validator__label__source__id?: InputMaybe<Scalars["ID"]>;
  validator__label__value?: InputMaybe<Scalars["String"]>;
  validator__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  validator__started_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  validator__started_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  validator__started_at__owner__id?: InputMaybe<Scalars["ID"]>;
  validator__started_at__source__id?: InputMaybe<Scalars["ID"]>;
  validator__started_at__value?: InputMaybe<Scalars["String"]>;
  validator__started_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  validator__state__is_protected?: InputMaybe<Scalars["Boolean"]>;
  validator__state__is_visible?: InputMaybe<Scalars["Boolean"]>;
  validator__state__owner__id?: InputMaybe<Scalars["ID"]>;
  validator__state__source__id?: InputMaybe<Scalars["ID"]>;
  validator__state__value?: InputMaybe<Scalars["String"]>;
  validator__state__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryCoreFileThreadArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  change__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  change__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  change__description__owner__id?: InputMaybe<Scalars["ID"]>;
  change__description__source__id?: InputMaybe<Scalars["ID"]>;
  change__description__value?: InputMaybe<Scalars["String"]>;
  change__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  change__destination_branch__is_protected?: InputMaybe<Scalars["Boolean"]>;
  change__destination_branch__is_visible?: InputMaybe<Scalars["Boolean"]>;
  change__destination_branch__owner__id?: InputMaybe<Scalars["ID"]>;
  change__destination_branch__source__id?: InputMaybe<Scalars["ID"]>;
  change__destination_branch__value?: InputMaybe<Scalars["String"]>;
  change__destination_branch__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  change__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  change__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  change__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  change__name__owner__id?: InputMaybe<Scalars["ID"]>;
  change__name__source__id?: InputMaybe<Scalars["ID"]>;
  change__name__value?: InputMaybe<Scalars["String"]>;
  change__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  change__source_branch__is_protected?: InputMaybe<Scalars["Boolean"]>;
  change__source_branch__is_visible?: InputMaybe<Scalars["Boolean"]>;
  change__source_branch__owner__id?: InputMaybe<Scalars["ID"]>;
  change__source_branch__source__id?: InputMaybe<Scalars["ID"]>;
  change__source_branch__value?: InputMaybe<Scalars["String"]>;
  change__source_branch__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  change__state__is_protected?: InputMaybe<Scalars["Boolean"]>;
  change__state__is_visible?: InputMaybe<Scalars["Boolean"]>;
  change__state__owner__id?: InputMaybe<Scalars["ID"]>;
  change__state__source__id?: InputMaybe<Scalars["ID"]>;
  change__state__value?: InputMaybe<Scalars["String"]>;
  change__state__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  comments__created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  comments__created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  comments__created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  comments__created_at__source__id?: InputMaybe<Scalars["ID"]>;
  comments__created_at__value?: InputMaybe<Scalars["String"]>;
  comments__created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  comments__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  comments__text__is_protected?: InputMaybe<Scalars["Boolean"]>;
  comments__text__is_visible?: InputMaybe<Scalars["Boolean"]>;
  comments__text__owner__id?: InputMaybe<Scalars["ID"]>;
  comments__text__source__id?: InputMaybe<Scalars["ID"]>;
  comments__text__value?: InputMaybe<Scalars["String"]>;
  comments__text__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  commit__is_protected?: InputMaybe<Scalars["Boolean"]>;
  commit__is_visible?: InputMaybe<Scalars["Boolean"]>;
  commit__owner__id?: InputMaybe<Scalars["ID"]>;
  commit__source__id?: InputMaybe<Scalars["ID"]>;
  commit__value?: InputMaybe<Scalars["String"]>;
  commit__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  created_at__source__id?: InputMaybe<Scalars["ID"]>;
  created_at__value?: InputMaybe<Scalars["String"]>;
  created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__description__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__description__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__description__value?: InputMaybe<Scalars["String"]>;
  created_by__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  created_by__label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__label__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__label__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__label__value?: InputMaybe<Scalars["String"]>;
  created_by__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__name__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__name__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__name__value?: InputMaybe<Scalars["String"]>;
  created_by__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__password__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__password__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__password__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__password__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__password__value?: InputMaybe<Scalars["String"]>;
  created_by__password__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__role__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__role__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__role__value?: InputMaybe<Scalars["String"]>;
  created_by__role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__type__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__type__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__type__value?: InputMaybe<Scalars["String"]>;
  created_by__type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  file__is_protected?: InputMaybe<Scalars["Boolean"]>;
  file__is_visible?: InputMaybe<Scalars["Boolean"]>;
  file__owner__id?: InputMaybe<Scalars["ID"]>;
  file__source__id?: InputMaybe<Scalars["ID"]>;
  file__value?: InputMaybe<Scalars["String"]>;
  file__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  line_number__is_protected?: InputMaybe<Scalars["Boolean"]>;
  line_number__is_visible?: InputMaybe<Scalars["Boolean"]>;
  line_number__owner__id?: InputMaybe<Scalars["ID"]>;
  line_number__source__id?: InputMaybe<Scalars["ID"]>;
  line_number__value?: InputMaybe<Scalars["Int"]>;
  line_number__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  repository__commit__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__commit__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__commit__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__commit__source__id?: InputMaybe<Scalars["ID"]>;
  repository__commit__value?: InputMaybe<Scalars["String"]>;
  repository__commit__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  repository__default_branch__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__default_branch__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__default_branch__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__default_branch__source__id?: InputMaybe<Scalars["ID"]>;
  repository__default_branch__value?: InputMaybe<Scalars["String"]>;
  repository__default_branch__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  repository__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__description__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__description__source__id?: InputMaybe<Scalars["ID"]>;
  repository__description__value?: InputMaybe<Scalars["String"]>;
  repository__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  repository__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  repository__location__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__location__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__location__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__location__source__id?: InputMaybe<Scalars["ID"]>;
  repository__location__value?: InputMaybe<Scalars["String"]>;
  repository__location__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  repository__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__name__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__name__source__id?: InputMaybe<Scalars["ID"]>;
  repository__name__value?: InputMaybe<Scalars["String"]>;
  repository__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  repository__password__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__password__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__password__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__password__source__id?: InputMaybe<Scalars["ID"]>;
  repository__password__value?: InputMaybe<Scalars["String"]>;
  repository__password__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  repository__username__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__username__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__username__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__username__source__id?: InputMaybe<Scalars["ID"]>;
  repository__username__value?: InputMaybe<Scalars["String"]>;
  repository__username__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  resolved__is_protected?: InputMaybe<Scalars["Boolean"]>;
  resolved__is_visible?: InputMaybe<Scalars["Boolean"]>;
  resolved__owner__id?: InputMaybe<Scalars["ID"]>;
  resolved__source__id?: InputMaybe<Scalars["ID"]>;
  resolved__value?: InputMaybe<Scalars["Boolean"]>;
  resolved__values?: InputMaybe<Array<InputMaybe<Scalars["Boolean"]>>>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryCoreGenericRepositoryArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__class_name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__class_name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__class_name__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__class_name__source__id?: InputMaybe<Scalars["ID"]>;
  checks__class_name__value?: InputMaybe<Scalars["String"]>;
  checks__class_name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__description__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__description__source__id?: InputMaybe<Scalars["ID"]>;
  checks__description__value?: InputMaybe<Scalars["String"]>;
  checks__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__file_path__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__file_path__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__file_path__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__file_path__source__id?: InputMaybe<Scalars["ID"]>;
  checks__file_path__value?: InputMaybe<Scalars["String"]>;
  checks__file_path__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  checks__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__name__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__name__source__id?: InputMaybe<Scalars["ID"]>;
  checks__name__value?: InputMaybe<Scalars["String"]>;
  checks__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__parameters__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__parameters__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__parameters__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__parameters__source__id?: InputMaybe<Scalars["ID"]>;
  checks__parameters__value?: InputMaybe<Scalars["GenericScalar"]>;
  checks__parameters__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  checks__timeout__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__timeout__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__timeout__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__timeout__source__id?: InputMaybe<Scalars["ID"]>;
  checks__timeout__value?: InputMaybe<Scalars["Int"]>;
  checks__timeout__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  location__is_protected?: InputMaybe<Scalars["Boolean"]>;
  location__is_visible?: InputMaybe<Scalars["Boolean"]>;
  location__owner__id?: InputMaybe<Scalars["ID"]>;
  location__source__id?: InputMaybe<Scalars["ID"]>;
  location__value?: InputMaybe<Scalars["String"]>;
  location__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  password__is_protected?: InputMaybe<Scalars["Boolean"]>;
  password__is_visible?: InputMaybe<Scalars["Boolean"]>;
  password__owner__id?: InputMaybe<Scalars["ID"]>;
  password__source__id?: InputMaybe<Scalars["ID"]>;
  password__value?: InputMaybe<Scalars["String"]>;
  password__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  queries__depth__is_protected?: InputMaybe<Scalars["Boolean"]>;
  queries__depth__is_visible?: InputMaybe<Scalars["Boolean"]>;
  queries__depth__owner__id?: InputMaybe<Scalars["ID"]>;
  queries__depth__source__id?: InputMaybe<Scalars["ID"]>;
  queries__depth__value?: InputMaybe<Scalars["Int"]>;
  queries__depth__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  queries__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  queries__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  queries__description__owner__id?: InputMaybe<Scalars["ID"]>;
  queries__description__source__id?: InputMaybe<Scalars["ID"]>;
  queries__description__value?: InputMaybe<Scalars["String"]>;
  queries__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  queries__height__is_protected?: InputMaybe<Scalars["Boolean"]>;
  queries__height__is_visible?: InputMaybe<Scalars["Boolean"]>;
  queries__height__owner__id?: InputMaybe<Scalars["ID"]>;
  queries__height__source__id?: InputMaybe<Scalars["ID"]>;
  queries__height__value?: InputMaybe<Scalars["Int"]>;
  queries__height__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  queries__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  queries__models__is_protected?: InputMaybe<Scalars["Boolean"]>;
  queries__models__is_visible?: InputMaybe<Scalars["Boolean"]>;
  queries__models__owner__id?: InputMaybe<Scalars["ID"]>;
  queries__models__source__id?: InputMaybe<Scalars["ID"]>;
  queries__models__value?: InputMaybe<Scalars["GenericScalar"]>;
  queries__models__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  queries__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  queries__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  queries__name__owner__id?: InputMaybe<Scalars["ID"]>;
  queries__name__source__id?: InputMaybe<Scalars["ID"]>;
  queries__name__value?: InputMaybe<Scalars["String"]>;
  queries__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  queries__operations__is_protected?: InputMaybe<Scalars["Boolean"]>;
  queries__operations__is_visible?: InputMaybe<Scalars["Boolean"]>;
  queries__operations__owner__id?: InputMaybe<Scalars["ID"]>;
  queries__operations__source__id?: InputMaybe<Scalars["ID"]>;
  queries__operations__value?: InputMaybe<Scalars["GenericScalar"]>;
  queries__operations__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  queries__query__is_protected?: InputMaybe<Scalars["Boolean"]>;
  queries__query__is_visible?: InputMaybe<Scalars["Boolean"]>;
  queries__query__owner__id?: InputMaybe<Scalars["ID"]>;
  queries__query__source__id?: InputMaybe<Scalars["ID"]>;
  queries__query__value?: InputMaybe<Scalars["String"]>;
  queries__query__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  queries__variables__is_protected?: InputMaybe<Scalars["Boolean"]>;
  queries__variables__is_visible?: InputMaybe<Scalars["Boolean"]>;
  queries__variables__owner__id?: InputMaybe<Scalars["ID"]>;
  queries__variables__source__id?: InputMaybe<Scalars["ID"]>;
  queries__variables__value?: InputMaybe<Scalars["GenericScalar"]>;
  queries__variables__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  tags__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  tags__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  tags__description__owner__id?: InputMaybe<Scalars["ID"]>;
  tags__description__source__id?: InputMaybe<Scalars["ID"]>;
  tags__description__value?: InputMaybe<Scalars["String"]>;
  tags__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  tags__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  tags__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  tags__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  tags__name__owner__id?: InputMaybe<Scalars["ID"]>;
  tags__name__source__id?: InputMaybe<Scalars["ID"]>;
  tags__name__value?: InputMaybe<Scalars["String"]>;
  tags__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  transformations__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  transformations__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  transformations__description__owner__id?: InputMaybe<Scalars["ID"]>;
  transformations__description__source__id?: InputMaybe<Scalars["ID"]>;
  transformations__description__value?: InputMaybe<Scalars["String"]>;
  transformations__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  transformations__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  transformations__label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  transformations__label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  transformations__label__owner__id?: InputMaybe<Scalars["ID"]>;
  transformations__label__source__id?: InputMaybe<Scalars["ID"]>;
  transformations__label__value?: InputMaybe<Scalars["String"]>;
  transformations__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  transformations__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  transformations__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  transformations__name__owner__id?: InputMaybe<Scalars["ID"]>;
  transformations__name__source__id?: InputMaybe<Scalars["ID"]>;
  transformations__name__value?: InputMaybe<Scalars["String"]>;
  transformations__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  transformations__timeout__is_protected?: InputMaybe<Scalars["Boolean"]>;
  transformations__timeout__is_visible?: InputMaybe<Scalars["Boolean"]>;
  transformations__timeout__owner__id?: InputMaybe<Scalars["ID"]>;
  transformations__timeout__source__id?: InputMaybe<Scalars["ID"]>;
  transformations__timeout__value?: InputMaybe<Scalars["Int"]>;
  transformations__timeout__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  username__is_protected?: InputMaybe<Scalars["Boolean"]>;
  username__is_visible?: InputMaybe<Scalars["Boolean"]>;
  username__owner__id?: InputMaybe<Scalars["ID"]>;
  username__source__id?: InputMaybe<Scalars["ID"]>;
  username__value?: InputMaybe<Scalars["String"]>;
  username__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryCoreGraphQlQueryArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  depth__is_protected?: InputMaybe<Scalars["Boolean"]>;
  depth__is_visible?: InputMaybe<Scalars["Boolean"]>;
  depth__owner__id?: InputMaybe<Scalars["ID"]>;
  depth__source__id?: InputMaybe<Scalars["ID"]>;
  depth__value?: InputMaybe<Scalars["Int"]>;
  depth__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  height__is_protected?: InputMaybe<Scalars["Boolean"]>;
  height__is_visible?: InputMaybe<Scalars["Boolean"]>;
  height__owner__id?: InputMaybe<Scalars["ID"]>;
  height__source__id?: InputMaybe<Scalars["ID"]>;
  height__value?: InputMaybe<Scalars["Int"]>;
  height__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  models__is_protected?: InputMaybe<Scalars["Boolean"]>;
  models__is_visible?: InputMaybe<Scalars["Boolean"]>;
  models__owner__id?: InputMaybe<Scalars["ID"]>;
  models__source__id?: InputMaybe<Scalars["ID"]>;
  models__value?: InputMaybe<Scalars["GenericScalar"]>;
  models__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  operations__is_protected?: InputMaybe<Scalars["Boolean"]>;
  operations__is_visible?: InputMaybe<Scalars["Boolean"]>;
  operations__owner__id?: InputMaybe<Scalars["ID"]>;
  operations__source__id?: InputMaybe<Scalars["ID"]>;
  operations__value?: InputMaybe<Scalars["GenericScalar"]>;
  operations__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  query__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__owner__id?: InputMaybe<Scalars["ID"]>;
  query__source__id?: InputMaybe<Scalars["ID"]>;
  query__value?: InputMaybe<Scalars["String"]>;
  query__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  repository__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__description__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__description__source__id?: InputMaybe<Scalars["ID"]>;
  repository__description__value?: InputMaybe<Scalars["String"]>;
  repository__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  repository__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  repository__location__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__location__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__location__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__location__source__id?: InputMaybe<Scalars["ID"]>;
  repository__location__value?: InputMaybe<Scalars["String"]>;
  repository__location__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  repository__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__name__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__name__source__id?: InputMaybe<Scalars["ID"]>;
  repository__name__value?: InputMaybe<Scalars["String"]>;
  repository__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  repository__password__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__password__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__password__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__password__source__id?: InputMaybe<Scalars["ID"]>;
  repository__password__value?: InputMaybe<Scalars["String"]>;
  repository__password__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  repository__username__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__username__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__username__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__username__source__id?: InputMaybe<Scalars["ID"]>;
  repository__username__value?: InputMaybe<Scalars["String"]>;
  repository__username__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  tags__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  tags__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  tags__description__owner__id?: InputMaybe<Scalars["ID"]>;
  tags__description__source__id?: InputMaybe<Scalars["ID"]>;
  tags__description__value?: InputMaybe<Scalars["String"]>;
  tags__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  tags__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  tags__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  tags__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  tags__name__owner__id?: InputMaybe<Scalars["ID"]>;
  tags__name__source__id?: InputMaybe<Scalars["ID"]>;
  tags__name__value?: InputMaybe<Scalars["String"]>;
  tags__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  variables__is_protected?: InputMaybe<Scalars["Boolean"]>;
  variables__is_visible?: InputMaybe<Scalars["Boolean"]>;
  variables__owner__id?: InputMaybe<Scalars["ID"]>;
  variables__source__id?: InputMaybe<Scalars["ID"]>;
  variables__value?: InputMaybe<Scalars["GenericScalar"]>;
  variables__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
};

export type QueryCoreGraphQlQueryGroupArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  children__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  children__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  children__description__owner__id?: InputMaybe<Scalars["ID"]>;
  children__description__source__id?: InputMaybe<Scalars["ID"]>;
  children__description__value?: InputMaybe<Scalars["String"]>;
  children__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  children__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  children__label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  children__label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  children__label__owner__id?: InputMaybe<Scalars["ID"]>;
  children__label__source__id?: InputMaybe<Scalars["ID"]>;
  children__label__value?: InputMaybe<Scalars["String"]>;
  children__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  children__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  children__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  children__name__owner__id?: InputMaybe<Scalars["ID"]>;
  children__name__source__id?: InputMaybe<Scalars["ID"]>;
  children__name__value?: InputMaybe<Scalars["String"]>;
  children__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  members__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  parameters__is_protected?: InputMaybe<Scalars["Boolean"]>;
  parameters__is_visible?: InputMaybe<Scalars["Boolean"]>;
  parameters__owner__id?: InputMaybe<Scalars["ID"]>;
  parameters__source__id?: InputMaybe<Scalars["ID"]>;
  parameters__value?: InputMaybe<Scalars["GenericScalar"]>;
  parameters__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  parent__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  parent__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  parent__description__owner__id?: InputMaybe<Scalars["ID"]>;
  parent__description__source__id?: InputMaybe<Scalars["ID"]>;
  parent__description__value?: InputMaybe<Scalars["String"]>;
  parent__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  parent__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  parent__label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  parent__label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  parent__label__owner__id?: InputMaybe<Scalars["ID"]>;
  parent__label__source__id?: InputMaybe<Scalars["ID"]>;
  parent__label__value?: InputMaybe<Scalars["String"]>;
  parent__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  parent__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  parent__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  parent__name__owner__id?: InputMaybe<Scalars["ID"]>;
  parent__name__source__id?: InputMaybe<Scalars["ID"]>;
  parent__name__value?: InputMaybe<Scalars["String"]>;
  parent__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  query__depth__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__depth__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__depth__owner__id?: InputMaybe<Scalars["ID"]>;
  query__depth__source__id?: InputMaybe<Scalars["ID"]>;
  query__depth__value?: InputMaybe<Scalars["Int"]>;
  query__depth__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  query__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__description__owner__id?: InputMaybe<Scalars["ID"]>;
  query__description__source__id?: InputMaybe<Scalars["ID"]>;
  query__description__value?: InputMaybe<Scalars["String"]>;
  query__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  query__height__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__height__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__height__owner__id?: InputMaybe<Scalars["ID"]>;
  query__height__source__id?: InputMaybe<Scalars["ID"]>;
  query__height__value?: InputMaybe<Scalars["Int"]>;
  query__height__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  query__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  query__models__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__models__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__models__owner__id?: InputMaybe<Scalars["ID"]>;
  query__models__source__id?: InputMaybe<Scalars["ID"]>;
  query__models__value?: InputMaybe<Scalars["GenericScalar"]>;
  query__models__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  query__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__name__owner__id?: InputMaybe<Scalars["ID"]>;
  query__name__source__id?: InputMaybe<Scalars["ID"]>;
  query__name__value?: InputMaybe<Scalars["String"]>;
  query__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  query__operations__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__operations__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__operations__owner__id?: InputMaybe<Scalars["ID"]>;
  query__operations__source__id?: InputMaybe<Scalars["ID"]>;
  query__operations__value?: InputMaybe<Scalars["GenericScalar"]>;
  query__operations__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  query__query__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__query__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__query__owner__id?: InputMaybe<Scalars["ID"]>;
  query__query__source__id?: InputMaybe<Scalars["ID"]>;
  query__query__value?: InputMaybe<Scalars["String"]>;
  query__query__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  query__variables__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__variables__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__variables__owner__id?: InputMaybe<Scalars["ID"]>;
  query__variables__source__id?: InputMaybe<Scalars["ID"]>;
  query__variables__value?: InputMaybe<Scalars["GenericScalar"]>;
  query__variables__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  subscribers__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
};

export type QueryCoreGroupArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  members__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  subscribers__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
};

export type QueryCoreNodeArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryCoreObjectThreadArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  change__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  change__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  change__description__owner__id?: InputMaybe<Scalars["ID"]>;
  change__description__source__id?: InputMaybe<Scalars["ID"]>;
  change__description__value?: InputMaybe<Scalars["String"]>;
  change__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  change__destination_branch__is_protected?: InputMaybe<Scalars["Boolean"]>;
  change__destination_branch__is_visible?: InputMaybe<Scalars["Boolean"]>;
  change__destination_branch__owner__id?: InputMaybe<Scalars["ID"]>;
  change__destination_branch__source__id?: InputMaybe<Scalars["ID"]>;
  change__destination_branch__value?: InputMaybe<Scalars["String"]>;
  change__destination_branch__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  change__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  change__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  change__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  change__name__owner__id?: InputMaybe<Scalars["ID"]>;
  change__name__source__id?: InputMaybe<Scalars["ID"]>;
  change__name__value?: InputMaybe<Scalars["String"]>;
  change__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  change__source_branch__is_protected?: InputMaybe<Scalars["Boolean"]>;
  change__source_branch__is_visible?: InputMaybe<Scalars["Boolean"]>;
  change__source_branch__owner__id?: InputMaybe<Scalars["ID"]>;
  change__source_branch__source__id?: InputMaybe<Scalars["ID"]>;
  change__source_branch__value?: InputMaybe<Scalars["String"]>;
  change__source_branch__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  change__state__is_protected?: InputMaybe<Scalars["Boolean"]>;
  change__state__is_visible?: InputMaybe<Scalars["Boolean"]>;
  change__state__owner__id?: InputMaybe<Scalars["ID"]>;
  change__state__source__id?: InputMaybe<Scalars["ID"]>;
  change__state__value?: InputMaybe<Scalars["String"]>;
  change__state__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  comments__created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  comments__created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  comments__created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  comments__created_at__source__id?: InputMaybe<Scalars["ID"]>;
  comments__created_at__value?: InputMaybe<Scalars["String"]>;
  comments__created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  comments__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  comments__text__is_protected?: InputMaybe<Scalars["Boolean"]>;
  comments__text__is_visible?: InputMaybe<Scalars["Boolean"]>;
  comments__text__owner__id?: InputMaybe<Scalars["ID"]>;
  comments__text__source__id?: InputMaybe<Scalars["ID"]>;
  comments__text__value?: InputMaybe<Scalars["String"]>;
  comments__text__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  created_at__source__id?: InputMaybe<Scalars["ID"]>;
  created_at__value?: InputMaybe<Scalars["String"]>;
  created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__description__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__description__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__description__value?: InputMaybe<Scalars["String"]>;
  created_by__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  created_by__label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__label__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__label__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__label__value?: InputMaybe<Scalars["String"]>;
  created_by__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__name__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__name__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__name__value?: InputMaybe<Scalars["String"]>;
  created_by__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__password__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__password__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__password__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__password__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__password__value?: InputMaybe<Scalars["String"]>;
  created_by__password__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__role__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__role__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__role__value?: InputMaybe<Scalars["String"]>;
  created_by__role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__type__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__type__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__type__value?: InputMaybe<Scalars["String"]>;
  created_by__type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  object_path__is_protected?: InputMaybe<Scalars["Boolean"]>;
  object_path__is_visible?: InputMaybe<Scalars["Boolean"]>;
  object_path__owner__id?: InputMaybe<Scalars["ID"]>;
  object_path__source__id?: InputMaybe<Scalars["ID"]>;
  object_path__value?: InputMaybe<Scalars["String"]>;
  object_path__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  resolved__is_protected?: InputMaybe<Scalars["Boolean"]>;
  resolved__is_visible?: InputMaybe<Scalars["Boolean"]>;
  resolved__owner__id?: InputMaybe<Scalars["ID"]>;
  resolved__source__id?: InputMaybe<Scalars["ID"]>;
  resolved__value?: InputMaybe<Scalars["Boolean"]>;
  resolved__values?: InputMaybe<Array<InputMaybe<Scalars["Boolean"]>>>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryCoreOrganizationArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  tags__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  tags__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  tags__description__owner__id?: InputMaybe<Scalars["ID"]>;
  tags__description__source__id?: InputMaybe<Scalars["ID"]>;
  tags__description__value?: InputMaybe<Scalars["String"]>;
  tags__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  tags__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  tags__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  tags__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  tags__name__owner__id?: InputMaybe<Scalars["ID"]>;
  tags__name__source__id?: InputMaybe<Scalars["ID"]>;
  tags__name__value?: InputMaybe<Scalars["String"]>;
  tags__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryCoreProposedChangeArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  approved_by__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  approved_by__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  approved_by__description__owner__id?: InputMaybe<Scalars["ID"]>;
  approved_by__description__source__id?: InputMaybe<Scalars["ID"]>;
  approved_by__description__value?: InputMaybe<Scalars["String"]>;
  approved_by__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  approved_by__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  approved_by__label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  approved_by__label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  approved_by__label__owner__id?: InputMaybe<Scalars["ID"]>;
  approved_by__label__source__id?: InputMaybe<Scalars["ID"]>;
  approved_by__label__value?: InputMaybe<Scalars["String"]>;
  approved_by__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  approved_by__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  approved_by__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  approved_by__name__owner__id?: InputMaybe<Scalars["ID"]>;
  approved_by__name__source__id?: InputMaybe<Scalars["ID"]>;
  approved_by__name__value?: InputMaybe<Scalars["String"]>;
  approved_by__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  approved_by__password__is_protected?: InputMaybe<Scalars["Boolean"]>;
  approved_by__password__is_visible?: InputMaybe<Scalars["Boolean"]>;
  approved_by__password__owner__id?: InputMaybe<Scalars["ID"]>;
  approved_by__password__source__id?: InputMaybe<Scalars["ID"]>;
  approved_by__password__value?: InputMaybe<Scalars["String"]>;
  approved_by__password__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  approved_by__role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  approved_by__role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  approved_by__role__owner__id?: InputMaybe<Scalars["ID"]>;
  approved_by__role__source__id?: InputMaybe<Scalars["ID"]>;
  approved_by__role__value?: InputMaybe<Scalars["String"]>;
  approved_by__role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  approved_by__type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  approved_by__type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  approved_by__type__owner__id?: InputMaybe<Scalars["ID"]>;
  approved_by__type__source__id?: InputMaybe<Scalars["ID"]>;
  approved_by__type__value?: InputMaybe<Scalars["String"]>;
  approved_by__type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  comments__created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  comments__created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  comments__created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  comments__created_at__source__id?: InputMaybe<Scalars["ID"]>;
  comments__created_at__value?: InputMaybe<Scalars["String"]>;
  comments__created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  comments__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  comments__text__is_protected?: InputMaybe<Scalars["Boolean"]>;
  comments__text__is_visible?: InputMaybe<Scalars["Boolean"]>;
  comments__text__owner__id?: InputMaybe<Scalars["ID"]>;
  comments__text__source__id?: InputMaybe<Scalars["ID"]>;
  comments__text__value?: InputMaybe<Scalars["String"]>;
  comments__text__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__description__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__description__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__description__value?: InputMaybe<Scalars["String"]>;
  created_by__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  created_by__label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__label__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__label__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__label__value?: InputMaybe<Scalars["String"]>;
  created_by__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__name__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__name__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__name__value?: InputMaybe<Scalars["String"]>;
  created_by__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__password__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__password__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__password__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__password__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__password__value?: InputMaybe<Scalars["String"]>;
  created_by__password__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__role__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__role__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__role__value?: InputMaybe<Scalars["String"]>;
  created_by__role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__type__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__type__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__type__value?: InputMaybe<Scalars["String"]>;
  created_by__type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  destination_branch__is_protected?: InputMaybe<Scalars["Boolean"]>;
  destination_branch__is_visible?: InputMaybe<Scalars["Boolean"]>;
  destination_branch__owner__id?: InputMaybe<Scalars["ID"]>;
  destination_branch__source__id?: InputMaybe<Scalars["ID"]>;
  destination_branch__value?: InputMaybe<Scalars["String"]>;
  destination_branch__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  reviewers__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  reviewers__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  reviewers__description__owner__id?: InputMaybe<Scalars["ID"]>;
  reviewers__description__source__id?: InputMaybe<Scalars["ID"]>;
  reviewers__description__value?: InputMaybe<Scalars["String"]>;
  reviewers__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  reviewers__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  reviewers__label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  reviewers__label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  reviewers__label__owner__id?: InputMaybe<Scalars["ID"]>;
  reviewers__label__source__id?: InputMaybe<Scalars["ID"]>;
  reviewers__label__value?: InputMaybe<Scalars["String"]>;
  reviewers__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  reviewers__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  reviewers__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  reviewers__name__owner__id?: InputMaybe<Scalars["ID"]>;
  reviewers__name__source__id?: InputMaybe<Scalars["ID"]>;
  reviewers__name__value?: InputMaybe<Scalars["String"]>;
  reviewers__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  reviewers__password__is_protected?: InputMaybe<Scalars["Boolean"]>;
  reviewers__password__is_visible?: InputMaybe<Scalars["Boolean"]>;
  reviewers__password__owner__id?: InputMaybe<Scalars["ID"]>;
  reviewers__password__source__id?: InputMaybe<Scalars["ID"]>;
  reviewers__password__value?: InputMaybe<Scalars["String"]>;
  reviewers__password__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  reviewers__role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  reviewers__role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  reviewers__role__owner__id?: InputMaybe<Scalars["ID"]>;
  reviewers__role__source__id?: InputMaybe<Scalars["ID"]>;
  reviewers__role__value?: InputMaybe<Scalars["String"]>;
  reviewers__role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  reviewers__type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  reviewers__type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  reviewers__type__owner__id?: InputMaybe<Scalars["ID"]>;
  reviewers__type__source__id?: InputMaybe<Scalars["ID"]>;
  reviewers__type__value?: InputMaybe<Scalars["String"]>;
  reviewers__type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  source_branch__is_protected?: InputMaybe<Scalars["Boolean"]>;
  source_branch__is_visible?: InputMaybe<Scalars["Boolean"]>;
  source_branch__owner__id?: InputMaybe<Scalars["ID"]>;
  source_branch__source__id?: InputMaybe<Scalars["ID"]>;
  source_branch__value?: InputMaybe<Scalars["String"]>;
  source_branch__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  state__is_protected?: InputMaybe<Scalars["Boolean"]>;
  state__is_visible?: InputMaybe<Scalars["Boolean"]>;
  state__owner__id?: InputMaybe<Scalars["ID"]>;
  state__source__id?: InputMaybe<Scalars["ID"]>;
  state__value?: InputMaybe<Scalars["String"]>;
  state__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  threads__created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  threads__created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  threads__created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  threads__created_at__source__id?: InputMaybe<Scalars["ID"]>;
  threads__created_at__value?: InputMaybe<Scalars["String"]>;
  threads__created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  threads__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  threads__label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  threads__label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  threads__label__owner__id?: InputMaybe<Scalars["ID"]>;
  threads__label__source__id?: InputMaybe<Scalars["ID"]>;
  threads__label__value?: InputMaybe<Scalars["String"]>;
  threads__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  threads__resolved__is_protected?: InputMaybe<Scalars["Boolean"]>;
  threads__resolved__is_visible?: InputMaybe<Scalars["Boolean"]>;
  threads__resolved__owner__id?: InputMaybe<Scalars["ID"]>;
  threads__resolved__source__id?: InputMaybe<Scalars["ID"]>;
  threads__resolved__value?: InputMaybe<Scalars["Boolean"]>;
  threads__resolved__values?: InputMaybe<Array<InputMaybe<Scalars["Boolean"]>>>;
  validations__completed_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  validations__completed_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  validations__completed_at__owner__id?: InputMaybe<Scalars["ID"]>;
  validations__completed_at__source__id?: InputMaybe<Scalars["ID"]>;
  validations__completed_at__value?: InputMaybe<Scalars["String"]>;
  validations__completed_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  validations__conclusion__is_protected?: InputMaybe<Scalars["Boolean"]>;
  validations__conclusion__is_visible?: InputMaybe<Scalars["Boolean"]>;
  validations__conclusion__owner__id?: InputMaybe<Scalars["ID"]>;
  validations__conclusion__source__id?: InputMaybe<Scalars["ID"]>;
  validations__conclusion__value?: InputMaybe<Scalars["String"]>;
  validations__conclusion__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  validations__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  validations__label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  validations__label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  validations__label__owner__id?: InputMaybe<Scalars["ID"]>;
  validations__label__source__id?: InputMaybe<Scalars["ID"]>;
  validations__label__value?: InputMaybe<Scalars["String"]>;
  validations__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  validations__started_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  validations__started_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  validations__started_at__owner__id?: InputMaybe<Scalars["ID"]>;
  validations__started_at__source__id?: InputMaybe<Scalars["ID"]>;
  validations__started_at__value?: InputMaybe<Scalars["String"]>;
  validations__started_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  validations__state__is_protected?: InputMaybe<Scalars["Boolean"]>;
  validations__state__is_visible?: InputMaybe<Scalars["Boolean"]>;
  validations__state__owner__id?: InputMaybe<Scalars["ID"]>;
  validations__state__source__id?: InputMaybe<Scalars["ID"]>;
  validations__state__value?: InputMaybe<Scalars["String"]>;
  validations__state__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryCoreReadOnlyRepositoryArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__class_name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__class_name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__class_name__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__class_name__source__id?: InputMaybe<Scalars["ID"]>;
  checks__class_name__value?: InputMaybe<Scalars["String"]>;
  checks__class_name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__description__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__description__source__id?: InputMaybe<Scalars["ID"]>;
  checks__description__value?: InputMaybe<Scalars["String"]>;
  checks__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__file_path__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__file_path__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__file_path__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__file_path__source__id?: InputMaybe<Scalars["ID"]>;
  checks__file_path__value?: InputMaybe<Scalars["String"]>;
  checks__file_path__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  checks__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__name__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__name__source__id?: InputMaybe<Scalars["ID"]>;
  checks__name__value?: InputMaybe<Scalars["String"]>;
  checks__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__parameters__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__parameters__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__parameters__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__parameters__source__id?: InputMaybe<Scalars["ID"]>;
  checks__parameters__value?: InputMaybe<Scalars["GenericScalar"]>;
  checks__parameters__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  checks__timeout__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__timeout__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__timeout__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__timeout__source__id?: InputMaybe<Scalars["ID"]>;
  checks__timeout__value?: InputMaybe<Scalars["Int"]>;
  checks__timeout__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  commit__is_protected?: InputMaybe<Scalars["Boolean"]>;
  commit__is_visible?: InputMaybe<Scalars["Boolean"]>;
  commit__owner__id?: InputMaybe<Scalars["ID"]>;
  commit__source__id?: InputMaybe<Scalars["ID"]>;
  commit__value?: InputMaybe<Scalars["String"]>;
  commit__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  location__is_protected?: InputMaybe<Scalars["Boolean"]>;
  location__is_visible?: InputMaybe<Scalars["Boolean"]>;
  location__owner__id?: InputMaybe<Scalars["ID"]>;
  location__source__id?: InputMaybe<Scalars["ID"]>;
  location__value?: InputMaybe<Scalars["String"]>;
  location__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  password__is_protected?: InputMaybe<Scalars["Boolean"]>;
  password__is_visible?: InputMaybe<Scalars["Boolean"]>;
  password__owner__id?: InputMaybe<Scalars["ID"]>;
  password__source__id?: InputMaybe<Scalars["ID"]>;
  password__value?: InputMaybe<Scalars["String"]>;
  password__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  queries__depth__is_protected?: InputMaybe<Scalars["Boolean"]>;
  queries__depth__is_visible?: InputMaybe<Scalars["Boolean"]>;
  queries__depth__owner__id?: InputMaybe<Scalars["ID"]>;
  queries__depth__source__id?: InputMaybe<Scalars["ID"]>;
  queries__depth__value?: InputMaybe<Scalars["Int"]>;
  queries__depth__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  queries__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  queries__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  queries__description__owner__id?: InputMaybe<Scalars["ID"]>;
  queries__description__source__id?: InputMaybe<Scalars["ID"]>;
  queries__description__value?: InputMaybe<Scalars["String"]>;
  queries__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  queries__height__is_protected?: InputMaybe<Scalars["Boolean"]>;
  queries__height__is_visible?: InputMaybe<Scalars["Boolean"]>;
  queries__height__owner__id?: InputMaybe<Scalars["ID"]>;
  queries__height__source__id?: InputMaybe<Scalars["ID"]>;
  queries__height__value?: InputMaybe<Scalars["Int"]>;
  queries__height__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  queries__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  queries__models__is_protected?: InputMaybe<Scalars["Boolean"]>;
  queries__models__is_visible?: InputMaybe<Scalars["Boolean"]>;
  queries__models__owner__id?: InputMaybe<Scalars["ID"]>;
  queries__models__source__id?: InputMaybe<Scalars["ID"]>;
  queries__models__value?: InputMaybe<Scalars["GenericScalar"]>;
  queries__models__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  queries__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  queries__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  queries__name__owner__id?: InputMaybe<Scalars["ID"]>;
  queries__name__source__id?: InputMaybe<Scalars["ID"]>;
  queries__name__value?: InputMaybe<Scalars["String"]>;
  queries__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  queries__operations__is_protected?: InputMaybe<Scalars["Boolean"]>;
  queries__operations__is_visible?: InputMaybe<Scalars["Boolean"]>;
  queries__operations__owner__id?: InputMaybe<Scalars["ID"]>;
  queries__operations__source__id?: InputMaybe<Scalars["ID"]>;
  queries__operations__value?: InputMaybe<Scalars["GenericScalar"]>;
  queries__operations__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  queries__query__is_protected?: InputMaybe<Scalars["Boolean"]>;
  queries__query__is_visible?: InputMaybe<Scalars["Boolean"]>;
  queries__query__owner__id?: InputMaybe<Scalars["ID"]>;
  queries__query__source__id?: InputMaybe<Scalars["ID"]>;
  queries__query__value?: InputMaybe<Scalars["String"]>;
  queries__query__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  queries__variables__is_protected?: InputMaybe<Scalars["Boolean"]>;
  queries__variables__is_visible?: InputMaybe<Scalars["Boolean"]>;
  queries__variables__owner__id?: InputMaybe<Scalars["ID"]>;
  queries__variables__source__id?: InputMaybe<Scalars["ID"]>;
  queries__variables__value?: InputMaybe<Scalars["GenericScalar"]>;
  queries__variables__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  ref__is_protected?: InputMaybe<Scalars["Boolean"]>;
  ref__is_visible?: InputMaybe<Scalars["Boolean"]>;
  ref__owner__id?: InputMaybe<Scalars["ID"]>;
  ref__source__id?: InputMaybe<Scalars["ID"]>;
  ref__value?: InputMaybe<Scalars["String"]>;
  ref__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  tags__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  tags__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  tags__description__owner__id?: InputMaybe<Scalars["ID"]>;
  tags__description__source__id?: InputMaybe<Scalars["ID"]>;
  tags__description__value?: InputMaybe<Scalars["String"]>;
  tags__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  tags__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  tags__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  tags__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  tags__name__owner__id?: InputMaybe<Scalars["ID"]>;
  tags__name__source__id?: InputMaybe<Scalars["ID"]>;
  tags__name__value?: InputMaybe<Scalars["String"]>;
  tags__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  transformations__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  transformations__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  transformations__description__owner__id?: InputMaybe<Scalars["ID"]>;
  transformations__description__source__id?: InputMaybe<Scalars["ID"]>;
  transformations__description__value?: InputMaybe<Scalars["String"]>;
  transformations__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  transformations__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  transformations__label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  transformations__label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  transformations__label__owner__id?: InputMaybe<Scalars["ID"]>;
  transformations__label__source__id?: InputMaybe<Scalars["ID"]>;
  transformations__label__value?: InputMaybe<Scalars["String"]>;
  transformations__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  transformations__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  transformations__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  transformations__name__owner__id?: InputMaybe<Scalars["ID"]>;
  transformations__name__source__id?: InputMaybe<Scalars["ID"]>;
  transformations__name__value?: InputMaybe<Scalars["String"]>;
  transformations__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  transformations__timeout__is_protected?: InputMaybe<Scalars["Boolean"]>;
  transformations__timeout__is_visible?: InputMaybe<Scalars["Boolean"]>;
  transformations__timeout__owner__id?: InputMaybe<Scalars["ID"]>;
  transformations__timeout__source__id?: InputMaybe<Scalars["ID"]>;
  transformations__timeout__value?: InputMaybe<Scalars["Int"]>;
  transformations__timeout__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  username__is_protected?: InputMaybe<Scalars["Boolean"]>;
  username__is_visible?: InputMaybe<Scalars["Boolean"]>;
  username__owner__id?: InputMaybe<Scalars["ID"]>;
  username__source__id?: InputMaybe<Scalars["ID"]>;
  username__value?: InputMaybe<Scalars["String"]>;
  username__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryCoreRepositoryArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__class_name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__class_name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__class_name__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__class_name__source__id?: InputMaybe<Scalars["ID"]>;
  checks__class_name__value?: InputMaybe<Scalars["String"]>;
  checks__class_name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__description__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__description__source__id?: InputMaybe<Scalars["ID"]>;
  checks__description__value?: InputMaybe<Scalars["String"]>;
  checks__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__file_path__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__file_path__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__file_path__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__file_path__source__id?: InputMaybe<Scalars["ID"]>;
  checks__file_path__value?: InputMaybe<Scalars["String"]>;
  checks__file_path__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  checks__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__name__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__name__source__id?: InputMaybe<Scalars["ID"]>;
  checks__name__value?: InputMaybe<Scalars["String"]>;
  checks__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__parameters__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__parameters__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__parameters__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__parameters__source__id?: InputMaybe<Scalars["ID"]>;
  checks__parameters__value?: InputMaybe<Scalars["GenericScalar"]>;
  checks__parameters__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  checks__timeout__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__timeout__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__timeout__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__timeout__source__id?: InputMaybe<Scalars["ID"]>;
  checks__timeout__value?: InputMaybe<Scalars["Int"]>;
  checks__timeout__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  commit__is_protected?: InputMaybe<Scalars["Boolean"]>;
  commit__is_visible?: InputMaybe<Scalars["Boolean"]>;
  commit__owner__id?: InputMaybe<Scalars["ID"]>;
  commit__source__id?: InputMaybe<Scalars["ID"]>;
  commit__value?: InputMaybe<Scalars["String"]>;
  commit__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  default_branch__is_protected?: InputMaybe<Scalars["Boolean"]>;
  default_branch__is_visible?: InputMaybe<Scalars["Boolean"]>;
  default_branch__owner__id?: InputMaybe<Scalars["ID"]>;
  default_branch__source__id?: InputMaybe<Scalars["ID"]>;
  default_branch__value?: InputMaybe<Scalars["String"]>;
  default_branch__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  location__is_protected?: InputMaybe<Scalars["Boolean"]>;
  location__is_visible?: InputMaybe<Scalars["Boolean"]>;
  location__owner__id?: InputMaybe<Scalars["ID"]>;
  location__source__id?: InputMaybe<Scalars["ID"]>;
  location__value?: InputMaybe<Scalars["String"]>;
  location__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  password__is_protected?: InputMaybe<Scalars["Boolean"]>;
  password__is_visible?: InputMaybe<Scalars["Boolean"]>;
  password__owner__id?: InputMaybe<Scalars["ID"]>;
  password__source__id?: InputMaybe<Scalars["ID"]>;
  password__value?: InputMaybe<Scalars["String"]>;
  password__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  queries__depth__is_protected?: InputMaybe<Scalars["Boolean"]>;
  queries__depth__is_visible?: InputMaybe<Scalars["Boolean"]>;
  queries__depth__owner__id?: InputMaybe<Scalars["ID"]>;
  queries__depth__source__id?: InputMaybe<Scalars["ID"]>;
  queries__depth__value?: InputMaybe<Scalars["Int"]>;
  queries__depth__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  queries__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  queries__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  queries__description__owner__id?: InputMaybe<Scalars["ID"]>;
  queries__description__source__id?: InputMaybe<Scalars["ID"]>;
  queries__description__value?: InputMaybe<Scalars["String"]>;
  queries__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  queries__height__is_protected?: InputMaybe<Scalars["Boolean"]>;
  queries__height__is_visible?: InputMaybe<Scalars["Boolean"]>;
  queries__height__owner__id?: InputMaybe<Scalars["ID"]>;
  queries__height__source__id?: InputMaybe<Scalars["ID"]>;
  queries__height__value?: InputMaybe<Scalars["Int"]>;
  queries__height__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  queries__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  queries__models__is_protected?: InputMaybe<Scalars["Boolean"]>;
  queries__models__is_visible?: InputMaybe<Scalars["Boolean"]>;
  queries__models__owner__id?: InputMaybe<Scalars["ID"]>;
  queries__models__source__id?: InputMaybe<Scalars["ID"]>;
  queries__models__value?: InputMaybe<Scalars["GenericScalar"]>;
  queries__models__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  queries__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  queries__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  queries__name__owner__id?: InputMaybe<Scalars["ID"]>;
  queries__name__source__id?: InputMaybe<Scalars["ID"]>;
  queries__name__value?: InputMaybe<Scalars["String"]>;
  queries__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  queries__operations__is_protected?: InputMaybe<Scalars["Boolean"]>;
  queries__operations__is_visible?: InputMaybe<Scalars["Boolean"]>;
  queries__operations__owner__id?: InputMaybe<Scalars["ID"]>;
  queries__operations__source__id?: InputMaybe<Scalars["ID"]>;
  queries__operations__value?: InputMaybe<Scalars["GenericScalar"]>;
  queries__operations__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  queries__query__is_protected?: InputMaybe<Scalars["Boolean"]>;
  queries__query__is_visible?: InputMaybe<Scalars["Boolean"]>;
  queries__query__owner__id?: InputMaybe<Scalars["ID"]>;
  queries__query__source__id?: InputMaybe<Scalars["ID"]>;
  queries__query__value?: InputMaybe<Scalars["String"]>;
  queries__query__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  queries__variables__is_protected?: InputMaybe<Scalars["Boolean"]>;
  queries__variables__is_visible?: InputMaybe<Scalars["Boolean"]>;
  queries__variables__owner__id?: InputMaybe<Scalars["ID"]>;
  queries__variables__source__id?: InputMaybe<Scalars["ID"]>;
  queries__variables__value?: InputMaybe<Scalars["GenericScalar"]>;
  queries__variables__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  tags__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  tags__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  tags__description__owner__id?: InputMaybe<Scalars["ID"]>;
  tags__description__source__id?: InputMaybe<Scalars["ID"]>;
  tags__description__value?: InputMaybe<Scalars["String"]>;
  tags__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  tags__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  tags__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  tags__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  tags__name__owner__id?: InputMaybe<Scalars["ID"]>;
  tags__name__source__id?: InputMaybe<Scalars["ID"]>;
  tags__name__value?: InputMaybe<Scalars["String"]>;
  tags__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  transformations__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  transformations__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  transformations__description__owner__id?: InputMaybe<Scalars["ID"]>;
  transformations__description__source__id?: InputMaybe<Scalars["ID"]>;
  transformations__description__value?: InputMaybe<Scalars["String"]>;
  transformations__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  transformations__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  transformations__label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  transformations__label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  transformations__label__owner__id?: InputMaybe<Scalars["ID"]>;
  transformations__label__source__id?: InputMaybe<Scalars["ID"]>;
  transformations__label__value?: InputMaybe<Scalars["String"]>;
  transformations__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  transformations__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  transformations__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  transformations__name__owner__id?: InputMaybe<Scalars["ID"]>;
  transformations__name__source__id?: InputMaybe<Scalars["ID"]>;
  transformations__name__value?: InputMaybe<Scalars["String"]>;
  transformations__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  transformations__timeout__is_protected?: InputMaybe<Scalars["Boolean"]>;
  transformations__timeout__is_visible?: InputMaybe<Scalars["Boolean"]>;
  transformations__timeout__owner__id?: InputMaybe<Scalars["ID"]>;
  transformations__timeout__source__id?: InputMaybe<Scalars["ID"]>;
  transformations__timeout__value?: InputMaybe<Scalars["Int"]>;
  transformations__timeout__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  username__is_protected?: InputMaybe<Scalars["Boolean"]>;
  username__is_visible?: InputMaybe<Scalars["Boolean"]>;
  username__owner__id?: InputMaybe<Scalars["ID"]>;
  username__source__id?: InputMaybe<Scalars["ID"]>;
  username__value?: InputMaybe<Scalars["String"]>;
  username__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryCoreRepositoryValidatorArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__conclusion__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__conclusion__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__conclusion__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__conclusion__source__id?: InputMaybe<Scalars["ID"]>;
  checks__conclusion__value?: InputMaybe<Scalars["String"]>;
  checks__conclusion__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__created_at__source__id?: InputMaybe<Scalars["ID"]>;
  checks__created_at__value?: InputMaybe<Scalars["String"]>;
  checks__created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  checks__kind__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__kind__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__kind__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__kind__source__id?: InputMaybe<Scalars["ID"]>;
  checks__kind__value?: InputMaybe<Scalars["String"]>;
  checks__kind__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__label__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__label__source__id?: InputMaybe<Scalars["ID"]>;
  checks__label__value?: InputMaybe<Scalars["String"]>;
  checks__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__message__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__message__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__message__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__message__source__id?: InputMaybe<Scalars["ID"]>;
  checks__message__value?: InputMaybe<Scalars["String"]>;
  checks__message__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__name__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__name__source__id?: InputMaybe<Scalars["ID"]>;
  checks__name__value?: InputMaybe<Scalars["String"]>;
  checks__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__origin__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__origin__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__origin__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__origin__source__id?: InputMaybe<Scalars["ID"]>;
  checks__origin__value?: InputMaybe<Scalars["String"]>;
  checks__origin__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__severity__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__severity__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__severity__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__severity__source__id?: InputMaybe<Scalars["ID"]>;
  checks__severity__value?: InputMaybe<Scalars["String"]>;
  checks__severity__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  completed_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  completed_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  completed_at__owner__id?: InputMaybe<Scalars["ID"]>;
  completed_at__source__id?: InputMaybe<Scalars["ID"]>;
  completed_at__value?: InputMaybe<Scalars["String"]>;
  completed_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  conclusion__is_protected?: InputMaybe<Scalars["Boolean"]>;
  conclusion__is_visible?: InputMaybe<Scalars["Boolean"]>;
  conclusion__owner__id?: InputMaybe<Scalars["ID"]>;
  conclusion__source__id?: InputMaybe<Scalars["ID"]>;
  conclusion__value?: InputMaybe<Scalars["String"]>;
  conclusion__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__description__owner__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__description__source__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__description__value?: InputMaybe<Scalars["String"]>;
  proposed_change__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  proposed_change__destination_branch__is_protected?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__destination_branch__is_visible?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__destination_branch__owner__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__destination_branch__source__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__destination_branch__value?: InputMaybe<Scalars["String"]>;
  proposed_change__destination_branch__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  proposed_change__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  proposed_change__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__name__owner__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__name__source__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__name__value?: InputMaybe<Scalars["String"]>;
  proposed_change__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  proposed_change__source_branch__is_protected?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__source_branch__is_visible?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__source_branch__owner__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__source_branch__source__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__source_branch__value?: InputMaybe<Scalars["String"]>;
  proposed_change__source_branch__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  proposed_change__state__is_protected?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__state__is_visible?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__state__owner__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__state__source__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__state__value?: InputMaybe<Scalars["String"]>;
  proposed_change__state__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  repository__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__description__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__description__source__id?: InputMaybe<Scalars["ID"]>;
  repository__description__value?: InputMaybe<Scalars["String"]>;
  repository__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  repository__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  repository__location__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__location__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__location__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__location__source__id?: InputMaybe<Scalars["ID"]>;
  repository__location__value?: InputMaybe<Scalars["String"]>;
  repository__location__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  repository__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__name__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__name__source__id?: InputMaybe<Scalars["ID"]>;
  repository__name__value?: InputMaybe<Scalars["String"]>;
  repository__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  repository__password__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__password__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__password__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__password__source__id?: InputMaybe<Scalars["ID"]>;
  repository__password__value?: InputMaybe<Scalars["String"]>;
  repository__password__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  repository__username__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__username__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__username__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__username__source__id?: InputMaybe<Scalars["ID"]>;
  repository__username__value?: InputMaybe<Scalars["String"]>;
  repository__username__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  started_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  started_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  started_at__owner__id?: InputMaybe<Scalars["ID"]>;
  started_at__source__id?: InputMaybe<Scalars["ID"]>;
  started_at__value?: InputMaybe<Scalars["String"]>;
  started_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  state__is_protected?: InputMaybe<Scalars["Boolean"]>;
  state__is_visible?: InputMaybe<Scalars["Boolean"]>;
  state__owner__id?: InputMaybe<Scalars["ID"]>;
  state__source__id?: InputMaybe<Scalars["ID"]>;
  state__value?: InputMaybe<Scalars["String"]>;
  state__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryCoreSchemaCheckArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  conclusion__is_protected?: InputMaybe<Scalars["Boolean"]>;
  conclusion__is_visible?: InputMaybe<Scalars["Boolean"]>;
  conclusion__owner__id?: InputMaybe<Scalars["ID"]>;
  conclusion__source__id?: InputMaybe<Scalars["ID"]>;
  conclusion__value?: InputMaybe<Scalars["String"]>;
  conclusion__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  conflicts__is_protected?: InputMaybe<Scalars["Boolean"]>;
  conflicts__is_visible?: InputMaybe<Scalars["Boolean"]>;
  conflicts__owner__id?: InputMaybe<Scalars["ID"]>;
  conflicts__source__id?: InputMaybe<Scalars["ID"]>;
  conflicts__value?: InputMaybe<Scalars["GenericScalar"]>;
  conflicts__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  created_at__source__id?: InputMaybe<Scalars["ID"]>;
  created_at__value?: InputMaybe<Scalars["String"]>;
  created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  kind__is_protected?: InputMaybe<Scalars["Boolean"]>;
  kind__is_visible?: InputMaybe<Scalars["Boolean"]>;
  kind__owner__id?: InputMaybe<Scalars["ID"]>;
  kind__source__id?: InputMaybe<Scalars["ID"]>;
  kind__value?: InputMaybe<Scalars["String"]>;
  kind__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  message__is_protected?: InputMaybe<Scalars["Boolean"]>;
  message__is_visible?: InputMaybe<Scalars["Boolean"]>;
  message__owner__id?: InputMaybe<Scalars["ID"]>;
  message__source__id?: InputMaybe<Scalars["ID"]>;
  message__value?: InputMaybe<Scalars["String"]>;
  message__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  origin__is_protected?: InputMaybe<Scalars["Boolean"]>;
  origin__is_visible?: InputMaybe<Scalars["Boolean"]>;
  origin__owner__id?: InputMaybe<Scalars["ID"]>;
  origin__source__id?: InputMaybe<Scalars["ID"]>;
  origin__value?: InputMaybe<Scalars["String"]>;
  origin__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  severity__is_protected?: InputMaybe<Scalars["Boolean"]>;
  severity__is_visible?: InputMaybe<Scalars["Boolean"]>;
  severity__owner__id?: InputMaybe<Scalars["ID"]>;
  severity__source__id?: InputMaybe<Scalars["ID"]>;
  severity__value?: InputMaybe<Scalars["String"]>;
  severity__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  validator__completed_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  validator__completed_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  validator__completed_at__owner__id?: InputMaybe<Scalars["ID"]>;
  validator__completed_at__source__id?: InputMaybe<Scalars["ID"]>;
  validator__completed_at__value?: InputMaybe<Scalars["String"]>;
  validator__completed_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  validator__conclusion__is_protected?: InputMaybe<Scalars["Boolean"]>;
  validator__conclusion__is_visible?: InputMaybe<Scalars["Boolean"]>;
  validator__conclusion__owner__id?: InputMaybe<Scalars["ID"]>;
  validator__conclusion__source__id?: InputMaybe<Scalars["ID"]>;
  validator__conclusion__value?: InputMaybe<Scalars["String"]>;
  validator__conclusion__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  validator__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  validator__label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  validator__label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  validator__label__owner__id?: InputMaybe<Scalars["ID"]>;
  validator__label__source__id?: InputMaybe<Scalars["ID"]>;
  validator__label__value?: InputMaybe<Scalars["String"]>;
  validator__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  validator__started_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  validator__started_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  validator__started_at__owner__id?: InputMaybe<Scalars["ID"]>;
  validator__started_at__source__id?: InputMaybe<Scalars["ID"]>;
  validator__started_at__value?: InputMaybe<Scalars["String"]>;
  validator__started_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  validator__state__is_protected?: InputMaybe<Scalars["Boolean"]>;
  validator__state__is_visible?: InputMaybe<Scalars["Boolean"]>;
  validator__state__owner__id?: InputMaybe<Scalars["ID"]>;
  validator__state__source__id?: InputMaybe<Scalars["ID"]>;
  validator__state__value?: InputMaybe<Scalars["String"]>;
  validator__state__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryCoreSchemaValidatorArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__conclusion__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__conclusion__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__conclusion__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__conclusion__source__id?: InputMaybe<Scalars["ID"]>;
  checks__conclusion__value?: InputMaybe<Scalars["String"]>;
  checks__conclusion__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__created_at__source__id?: InputMaybe<Scalars["ID"]>;
  checks__created_at__value?: InputMaybe<Scalars["String"]>;
  checks__created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  checks__kind__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__kind__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__kind__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__kind__source__id?: InputMaybe<Scalars["ID"]>;
  checks__kind__value?: InputMaybe<Scalars["String"]>;
  checks__kind__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__label__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__label__source__id?: InputMaybe<Scalars["ID"]>;
  checks__label__value?: InputMaybe<Scalars["String"]>;
  checks__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__message__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__message__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__message__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__message__source__id?: InputMaybe<Scalars["ID"]>;
  checks__message__value?: InputMaybe<Scalars["String"]>;
  checks__message__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__name__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__name__source__id?: InputMaybe<Scalars["ID"]>;
  checks__name__value?: InputMaybe<Scalars["String"]>;
  checks__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__origin__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__origin__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__origin__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__origin__source__id?: InputMaybe<Scalars["ID"]>;
  checks__origin__value?: InputMaybe<Scalars["String"]>;
  checks__origin__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__severity__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__severity__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__severity__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__severity__source__id?: InputMaybe<Scalars["ID"]>;
  checks__severity__value?: InputMaybe<Scalars["String"]>;
  checks__severity__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  completed_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  completed_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  completed_at__owner__id?: InputMaybe<Scalars["ID"]>;
  completed_at__source__id?: InputMaybe<Scalars["ID"]>;
  completed_at__value?: InputMaybe<Scalars["String"]>;
  completed_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  conclusion__is_protected?: InputMaybe<Scalars["Boolean"]>;
  conclusion__is_visible?: InputMaybe<Scalars["Boolean"]>;
  conclusion__owner__id?: InputMaybe<Scalars["ID"]>;
  conclusion__source__id?: InputMaybe<Scalars["ID"]>;
  conclusion__value?: InputMaybe<Scalars["String"]>;
  conclusion__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__description__owner__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__description__source__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__description__value?: InputMaybe<Scalars["String"]>;
  proposed_change__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  proposed_change__destination_branch__is_protected?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__destination_branch__is_visible?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__destination_branch__owner__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__destination_branch__source__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__destination_branch__value?: InputMaybe<Scalars["String"]>;
  proposed_change__destination_branch__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  proposed_change__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  proposed_change__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__name__owner__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__name__source__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__name__value?: InputMaybe<Scalars["String"]>;
  proposed_change__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  proposed_change__source_branch__is_protected?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__source_branch__is_visible?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__source_branch__owner__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__source_branch__source__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__source_branch__value?: InputMaybe<Scalars["String"]>;
  proposed_change__source_branch__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  proposed_change__state__is_protected?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__state__is_visible?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__state__owner__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__state__source__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__state__value?: InputMaybe<Scalars["String"]>;
  proposed_change__state__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  started_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  started_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  started_at__owner__id?: InputMaybe<Scalars["ID"]>;
  started_at__source__id?: InputMaybe<Scalars["ID"]>;
  started_at__value?: InputMaybe<Scalars["String"]>;
  started_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  state__is_protected?: InputMaybe<Scalars["Boolean"]>;
  state__is_visible?: InputMaybe<Scalars["Boolean"]>;
  state__owner__id?: InputMaybe<Scalars["ID"]>;
  state__source__id?: InputMaybe<Scalars["ID"]>;
  state__value?: InputMaybe<Scalars["String"]>;
  state__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryCoreStandardCheckArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  conclusion__is_protected?: InputMaybe<Scalars["Boolean"]>;
  conclusion__is_visible?: InputMaybe<Scalars["Boolean"]>;
  conclusion__owner__id?: InputMaybe<Scalars["ID"]>;
  conclusion__source__id?: InputMaybe<Scalars["ID"]>;
  conclusion__value?: InputMaybe<Scalars["String"]>;
  conclusion__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  created_at__source__id?: InputMaybe<Scalars["ID"]>;
  created_at__value?: InputMaybe<Scalars["String"]>;
  created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  kind__is_protected?: InputMaybe<Scalars["Boolean"]>;
  kind__is_visible?: InputMaybe<Scalars["Boolean"]>;
  kind__owner__id?: InputMaybe<Scalars["ID"]>;
  kind__source__id?: InputMaybe<Scalars["ID"]>;
  kind__value?: InputMaybe<Scalars["String"]>;
  kind__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  message__is_protected?: InputMaybe<Scalars["Boolean"]>;
  message__is_visible?: InputMaybe<Scalars["Boolean"]>;
  message__owner__id?: InputMaybe<Scalars["ID"]>;
  message__source__id?: InputMaybe<Scalars["ID"]>;
  message__value?: InputMaybe<Scalars["String"]>;
  message__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  origin__is_protected?: InputMaybe<Scalars["Boolean"]>;
  origin__is_visible?: InputMaybe<Scalars["Boolean"]>;
  origin__owner__id?: InputMaybe<Scalars["ID"]>;
  origin__source__id?: InputMaybe<Scalars["ID"]>;
  origin__value?: InputMaybe<Scalars["String"]>;
  origin__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  severity__is_protected?: InputMaybe<Scalars["Boolean"]>;
  severity__is_visible?: InputMaybe<Scalars["Boolean"]>;
  severity__owner__id?: InputMaybe<Scalars["ID"]>;
  severity__source__id?: InputMaybe<Scalars["ID"]>;
  severity__value?: InputMaybe<Scalars["String"]>;
  severity__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  validator__completed_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  validator__completed_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  validator__completed_at__owner__id?: InputMaybe<Scalars["ID"]>;
  validator__completed_at__source__id?: InputMaybe<Scalars["ID"]>;
  validator__completed_at__value?: InputMaybe<Scalars["String"]>;
  validator__completed_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  validator__conclusion__is_protected?: InputMaybe<Scalars["Boolean"]>;
  validator__conclusion__is_visible?: InputMaybe<Scalars["Boolean"]>;
  validator__conclusion__owner__id?: InputMaybe<Scalars["ID"]>;
  validator__conclusion__source__id?: InputMaybe<Scalars["ID"]>;
  validator__conclusion__value?: InputMaybe<Scalars["String"]>;
  validator__conclusion__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  validator__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  validator__label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  validator__label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  validator__label__owner__id?: InputMaybe<Scalars["ID"]>;
  validator__label__source__id?: InputMaybe<Scalars["ID"]>;
  validator__label__value?: InputMaybe<Scalars["String"]>;
  validator__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  validator__started_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  validator__started_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  validator__started_at__owner__id?: InputMaybe<Scalars["ID"]>;
  validator__started_at__source__id?: InputMaybe<Scalars["ID"]>;
  validator__started_at__value?: InputMaybe<Scalars["String"]>;
  validator__started_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  validator__state__is_protected?: InputMaybe<Scalars["Boolean"]>;
  validator__state__is_visible?: InputMaybe<Scalars["Boolean"]>;
  validator__state__owner__id?: InputMaybe<Scalars["ID"]>;
  validator__state__source__id?: InputMaybe<Scalars["ID"]>;
  validator__state__value?: InputMaybe<Scalars["String"]>;
  validator__state__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryCoreStandardGroupArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  children__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  children__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  children__description__owner__id?: InputMaybe<Scalars["ID"]>;
  children__description__source__id?: InputMaybe<Scalars["ID"]>;
  children__description__value?: InputMaybe<Scalars["String"]>;
  children__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  children__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  children__label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  children__label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  children__label__owner__id?: InputMaybe<Scalars["ID"]>;
  children__label__source__id?: InputMaybe<Scalars["ID"]>;
  children__label__value?: InputMaybe<Scalars["String"]>;
  children__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  children__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  children__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  children__name__owner__id?: InputMaybe<Scalars["ID"]>;
  children__name__source__id?: InputMaybe<Scalars["ID"]>;
  children__name__value?: InputMaybe<Scalars["String"]>;
  children__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  members__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  parent__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  parent__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  parent__description__owner__id?: InputMaybe<Scalars["ID"]>;
  parent__description__source__id?: InputMaybe<Scalars["ID"]>;
  parent__description__value?: InputMaybe<Scalars["String"]>;
  parent__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  parent__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  parent__label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  parent__label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  parent__label__owner__id?: InputMaybe<Scalars["ID"]>;
  parent__label__source__id?: InputMaybe<Scalars["ID"]>;
  parent__label__value?: InputMaybe<Scalars["String"]>;
  parent__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  parent__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  parent__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  parent__name__owner__id?: InputMaybe<Scalars["ID"]>;
  parent__name__source__id?: InputMaybe<Scalars["ID"]>;
  parent__name__value?: InputMaybe<Scalars["String"]>;
  parent__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  subscribers__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
};

export type QueryCoreStandardWebhookArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  shared_key__is_protected?: InputMaybe<Scalars["Boolean"]>;
  shared_key__is_visible?: InputMaybe<Scalars["Boolean"]>;
  shared_key__owner__id?: InputMaybe<Scalars["ID"]>;
  shared_key__source__id?: InputMaybe<Scalars["ID"]>;
  shared_key__value?: InputMaybe<Scalars["String"]>;
  shared_key__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  url__is_protected?: InputMaybe<Scalars["Boolean"]>;
  url__is_visible?: InputMaybe<Scalars["Boolean"]>;
  url__owner__id?: InputMaybe<Scalars["ID"]>;
  url__source__id?: InputMaybe<Scalars["ID"]>;
  url__value?: InputMaybe<Scalars["String"]>;
  url__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  validate_certificates__is_protected?: InputMaybe<Scalars["Boolean"]>;
  validate_certificates__is_visible?: InputMaybe<Scalars["Boolean"]>;
  validate_certificates__owner__id?: InputMaybe<Scalars["ID"]>;
  validate_certificates__source__id?: InputMaybe<Scalars["ID"]>;
  validate_certificates__value?: InputMaybe<Scalars["Boolean"]>;
  validate_certificates__values?: InputMaybe<Array<InputMaybe<Scalars["Boolean"]>>>;
};

export type QueryCoreTaskTargetArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryCoreThreadArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  change__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  change__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  change__description__owner__id?: InputMaybe<Scalars["ID"]>;
  change__description__source__id?: InputMaybe<Scalars["ID"]>;
  change__description__value?: InputMaybe<Scalars["String"]>;
  change__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  change__destination_branch__is_protected?: InputMaybe<Scalars["Boolean"]>;
  change__destination_branch__is_visible?: InputMaybe<Scalars["Boolean"]>;
  change__destination_branch__owner__id?: InputMaybe<Scalars["ID"]>;
  change__destination_branch__source__id?: InputMaybe<Scalars["ID"]>;
  change__destination_branch__value?: InputMaybe<Scalars["String"]>;
  change__destination_branch__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  change__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  change__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  change__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  change__name__owner__id?: InputMaybe<Scalars["ID"]>;
  change__name__source__id?: InputMaybe<Scalars["ID"]>;
  change__name__value?: InputMaybe<Scalars["String"]>;
  change__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  change__source_branch__is_protected?: InputMaybe<Scalars["Boolean"]>;
  change__source_branch__is_visible?: InputMaybe<Scalars["Boolean"]>;
  change__source_branch__owner__id?: InputMaybe<Scalars["ID"]>;
  change__source_branch__source__id?: InputMaybe<Scalars["ID"]>;
  change__source_branch__value?: InputMaybe<Scalars["String"]>;
  change__source_branch__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  change__state__is_protected?: InputMaybe<Scalars["Boolean"]>;
  change__state__is_visible?: InputMaybe<Scalars["Boolean"]>;
  change__state__owner__id?: InputMaybe<Scalars["ID"]>;
  change__state__source__id?: InputMaybe<Scalars["ID"]>;
  change__state__value?: InputMaybe<Scalars["String"]>;
  change__state__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  comments__created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  comments__created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  comments__created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  comments__created_at__source__id?: InputMaybe<Scalars["ID"]>;
  comments__created_at__value?: InputMaybe<Scalars["String"]>;
  comments__created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  comments__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  comments__text__is_protected?: InputMaybe<Scalars["Boolean"]>;
  comments__text__is_visible?: InputMaybe<Scalars["Boolean"]>;
  comments__text__owner__id?: InputMaybe<Scalars["ID"]>;
  comments__text__source__id?: InputMaybe<Scalars["ID"]>;
  comments__text__value?: InputMaybe<Scalars["String"]>;
  comments__text__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  created_at__source__id?: InputMaybe<Scalars["ID"]>;
  created_at__value?: InputMaybe<Scalars["String"]>;
  created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__description__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__description__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__description__value?: InputMaybe<Scalars["String"]>;
  created_by__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  created_by__label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__label__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__label__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__label__value?: InputMaybe<Scalars["String"]>;
  created_by__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__name__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__name__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__name__value?: InputMaybe<Scalars["String"]>;
  created_by__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__password__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__password__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__password__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__password__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__password__value?: InputMaybe<Scalars["String"]>;
  created_by__password__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__role__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__role__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__role__value?: InputMaybe<Scalars["String"]>;
  created_by__role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__type__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__type__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__type__value?: InputMaybe<Scalars["String"]>;
  created_by__type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  resolved__is_protected?: InputMaybe<Scalars["Boolean"]>;
  resolved__is_visible?: InputMaybe<Scalars["Boolean"]>;
  resolved__owner__id?: InputMaybe<Scalars["ID"]>;
  resolved__source__id?: InputMaybe<Scalars["ID"]>;
  resolved__value?: InputMaybe<Scalars["Boolean"]>;
  resolved__values?: InputMaybe<Array<InputMaybe<Scalars["Boolean"]>>>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryCoreThreadCommentArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  created_at__source__id?: InputMaybe<Scalars["ID"]>;
  created_at__value?: InputMaybe<Scalars["String"]>;
  created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__description__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__description__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__description__value?: InputMaybe<Scalars["String"]>;
  created_by__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  created_by__label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__label__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__label__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__label__value?: InputMaybe<Scalars["String"]>;
  created_by__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__name__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__name__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__name__value?: InputMaybe<Scalars["String"]>;
  created_by__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__password__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__password__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__password__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__password__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__password__value?: InputMaybe<Scalars["String"]>;
  created_by__password__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__role__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__role__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__role__value?: InputMaybe<Scalars["String"]>;
  created_by__role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  created_by__type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  created_by__type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  created_by__type__owner__id?: InputMaybe<Scalars["ID"]>;
  created_by__type__source__id?: InputMaybe<Scalars["ID"]>;
  created_by__type__value?: InputMaybe<Scalars["String"]>;
  created_by__type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  text__is_protected?: InputMaybe<Scalars["Boolean"]>;
  text__is_visible?: InputMaybe<Scalars["Boolean"]>;
  text__owner__id?: InputMaybe<Scalars["ID"]>;
  text__source__id?: InputMaybe<Scalars["ID"]>;
  text__value?: InputMaybe<Scalars["String"]>;
  text__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  thread__created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  thread__created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  thread__created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  thread__created_at__source__id?: InputMaybe<Scalars["ID"]>;
  thread__created_at__value?: InputMaybe<Scalars["String"]>;
  thread__created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  thread__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  thread__label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  thread__label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  thread__label__owner__id?: InputMaybe<Scalars["ID"]>;
  thread__label__source__id?: InputMaybe<Scalars["ID"]>;
  thread__label__value?: InputMaybe<Scalars["String"]>;
  thread__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  thread__resolved__is_protected?: InputMaybe<Scalars["Boolean"]>;
  thread__resolved__is_visible?: InputMaybe<Scalars["Boolean"]>;
  thread__resolved__owner__id?: InputMaybe<Scalars["ID"]>;
  thread__resolved__source__id?: InputMaybe<Scalars["ID"]>;
  thread__resolved__value?: InputMaybe<Scalars["Boolean"]>;
  thread__resolved__values?: InputMaybe<Array<InputMaybe<Scalars["Boolean"]>>>;
};

export type QueryCoreTransformJinja2Args = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  query__depth__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__depth__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__depth__owner__id?: InputMaybe<Scalars["ID"]>;
  query__depth__source__id?: InputMaybe<Scalars["ID"]>;
  query__depth__value?: InputMaybe<Scalars["Int"]>;
  query__depth__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  query__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__description__owner__id?: InputMaybe<Scalars["ID"]>;
  query__description__source__id?: InputMaybe<Scalars["ID"]>;
  query__description__value?: InputMaybe<Scalars["String"]>;
  query__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  query__height__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__height__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__height__owner__id?: InputMaybe<Scalars["ID"]>;
  query__height__source__id?: InputMaybe<Scalars["ID"]>;
  query__height__value?: InputMaybe<Scalars["Int"]>;
  query__height__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  query__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  query__models__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__models__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__models__owner__id?: InputMaybe<Scalars["ID"]>;
  query__models__source__id?: InputMaybe<Scalars["ID"]>;
  query__models__value?: InputMaybe<Scalars["GenericScalar"]>;
  query__models__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  query__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__name__owner__id?: InputMaybe<Scalars["ID"]>;
  query__name__source__id?: InputMaybe<Scalars["ID"]>;
  query__name__value?: InputMaybe<Scalars["String"]>;
  query__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  query__operations__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__operations__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__operations__owner__id?: InputMaybe<Scalars["ID"]>;
  query__operations__source__id?: InputMaybe<Scalars["ID"]>;
  query__operations__value?: InputMaybe<Scalars["GenericScalar"]>;
  query__operations__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  query__query__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__query__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__query__owner__id?: InputMaybe<Scalars["ID"]>;
  query__query__source__id?: InputMaybe<Scalars["ID"]>;
  query__query__value?: InputMaybe<Scalars["String"]>;
  query__query__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  query__variables__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__variables__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__variables__owner__id?: InputMaybe<Scalars["ID"]>;
  query__variables__source__id?: InputMaybe<Scalars["ID"]>;
  query__variables__value?: InputMaybe<Scalars["GenericScalar"]>;
  query__variables__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  repository__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__description__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__description__source__id?: InputMaybe<Scalars["ID"]>;
  repository__description__value?: InputMaybe<Scalars["String"]>;
  repository__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  repository__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  repository__location__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__location__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__location__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__location__source__id?: InputMaybe<Scalars["ID"]>;
  repository__location__value?: InputMaybe<Scalars["String"]>;
  repository__location__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  repository__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__name__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__name__source__id?: InputMaybe<Scalars["ID"]>;
  repository__name__value?: InputMaybe<Scalars["String"]>;
  repository__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  repository__password__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__password__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__password__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__password__source__id?: InputMaybe<Scalars["ID"]>;
  repository__password__value?: InputMaybe<Scalars["String"]>;
  repository__password__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  repository__username__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__username__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__username__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__username__source__id?: InputMaybe<Scalars["ID"]>;
  repository__username__value?: InputMaybe<Scalars["String"]>;
  repository__username__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  tags__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  tags__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  tags__description__owner__id?: InputMaybe<Scalars["ID"]>;
  tags__description__source__id?: InputMaybe<Scalars["ID"]>;
  tags__description__value?: InputMaybe<Scalars["String"]>;
  tags__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  tags__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  tags__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  tags__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  tags__name__owner__id?: InputMaybe<Scalars["ID"]>;
  tags__name__source__id?: InputMaybe<Scalars["ID"]>;
  tags__name__value?: InputMaybe<Scalars["String"]>;
  tags__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  template_path__is_protected?: InputMaybe<Scalars["Boolean"]>;
  template_path__is_visible?: InputMaybe<Scalars["Boolean"]>;
  template_path__owner__id?: InputMaybe<Scalars["ID"]>;
  template_path__source__id?: InputMaybe<Scalars["ID"]>;
  template_path__value?: InputMaybe<Scalars["String"]>;
  template_path__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  timeout__is_protected?: InputMaybe<Scalars["Boolean"]>;
  timeout__is_visible?: InputMaybe<Scalars["Boolean"]>;
  timeout__owner__id?: InputMaybe<Scalars["ID"]>;
  timeout__source__id?: InputMaybe<Scalars["ID"]>;
  timeout__value?: InputMaybe<Scalars["Int"]>;
  timeout__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
};

export type QueryCoreTransformPythonArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  class_name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  class_name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  class_name__owner__id?: InputMaybe<Scalars["ID"]>;
  class_name__source__id?: InputMaybe<Scalars["ID"]>;
  class_name__value?: InputMaybe<Scalars["String"]>;
  class_name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  file_path__is_protected?: InputMaybe<Scalars["Boolean"]>;
  file_path__is_visible?: InputMaybe<Scalars["Boolean"]>;
  file_path__owner__id?: InputMaybe<Scalars["ID"]>;
  file_path__source__id?: InputMaybe<Scalars["ID"]>;
  file_path__value?: InputMaybe<Scalars["String"]>;
  file_path__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  query__depth__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__depth__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__depth__owner__id?: InputMaybe<Scalars["ID"]>;
  query__depth__source__id?: InputMaybe<Scalars["ID"]>;
  query__depth__value?: InputMaybe<Scalars["Int"]>;
  query__depth__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  query__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__description__owner__id?: InputMaybe<Scalars["ID"]>;
  query__description__source__id?: InputMaybe<Scalars["ID"]>;
  query__description__value?: InputMaybe<Scalars["String"]>;
  query__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  query__height__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__height__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__height__owner__id?: InputMaybe<Scalars["ID"]>;
  query__height__source__id?: InputMaybe<Scalars["ID"]>;
  query__height__value?: InputMaybe<Scalars["Int"]>;
  query__height__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  query__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  query__models__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__models__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__models__owner__id?: InputMaybe<Scalars["ID"]>;
  query__models__source__id?: InputMaybe<Scalars["ID"]>;
  query__models__value?: InputMaybe<Scalars["GenericScalar"]>;
  query__models__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  query__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__name__owner__id?: InputMaybe<Scalars["ID"]>;
  query__name__source__id?: InputMaybe<Scalars["ID"]>;
  query__name__value?: InputMaybe<Scalars["String"]>;
  query__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  query__operations__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__operations__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__operations__owner__id?: InputMaybe<Scalars["ID"]>;
  query__operations__source__id?: InputMaybe<Scalars["ID"]>;
  query__operations__value?: InputMaybe<Scalars["GenericScalar"]>;
  query__operations__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  query__query__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__query__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__query__owner__id?: InputMaybe<Scalars["ID"]>;
  query__query__source__id?: InputMaybe<Scalars["ID"]>;
  query__query__value?: InputMaybe<Scalars["String"]>;
  query__query__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  query__variables__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__variables__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__variables__owner__id?: InputMaybe<Scalars["ID"]>;
  query__variables__source__id?: InputMaybe<Scalars["ID"]>;
  query__variables__value?: InputMaybe<Scalars["GenericScalar"]>;
  query__variables__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  repository__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__description__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__description__source__id?: InputMaybe<Scalars["ID"]>;
  repository__description__value?: InputMaybe<Scalars["String"]>;
  repository__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  repository__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  repository__location__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__location__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__location__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__location__source__id?: InputMaybe<Scalars["ID"]>;
  repository__location__value?: InputMaybe<Scalars["String"]>;
  repository__location__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  repository__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__name__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__name__source__id?: InputMaybe<Scalars["ID"]>;
  repository__name__value?: InputMaybe<Scalars["String"]>;
  repository__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  repository__password__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__password__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__password__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__password__source__id?: InputMaybe<Scalars["ID"]>;
  repository__password__value?: InputMaybe<Scalars["String"]>;
  repository__password__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  repository__username__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__username__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__username__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__username__source__id?: InputMaybe<Scalars["ID"]>;
  repository__username__value?: InputMaybe<Scalars["String"]>;
  repository__username__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  tags__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  tags__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  tags__description__owner__id?: InputMaybe<Scalars["ID"]>;
  tags__description__source__id?: InputMaybe<Scalars["ID"]>;
  tags__description__value?: InputMaybe<Scalars["String"]>;
  tags__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  tags__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  tags__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  tags__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  tags__name__owner__id?: InputMaybe<Scalars["ID"]>;
  tags__name__source__id?: InputMaybe<Scalars["ID"]>;
  tags__name__value?: InputMaybe<Scalars["String"]>;
  tags__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  timeout__is_protected?: InputMaybe<Scalars["Boolean"]>;
  timeout__is_visible?: InputMaybe<Scalars["Boolean"]>;
  timeout__owner__id?: InputMaybe<Scalars["ID"]>;
  timeout__source__id?: InputMaybe<Scalars["ID"]>;
  timeout__value?: InputMaybe<Scalars["Int"]>;
  timeout__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
};

export type QueryCoreTransformationArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  query__depth__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__depth__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__depth__owner__id?: InputMaybe<Scalars["ID"]>;
  query__depth__source__id?: InputMaybe<Scalars["ID"]>;
  query__depth__value?: InputMaybe<Scalars["Int"]>;
  query__depth__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  query__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__description__owner__id?: InputMaybe<Scalars["ID"]>;
  query__description__source__id?: InputMaybe<Scalars["ID"]>;
  query__description__value?: InputMaybe<Scalars["String"]>;
  query__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  query__height__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__height__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__height__owner__id?: InputMaybe<Scalars["ID"]>;
  query__height__source__id?: InputMaybe<Scalars["ID"]>;
  query__height__value?: InputMaybe<Scalars["Int"]>;
  query__height__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  query__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  query__models__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__models__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__models__owner__id?: InputMaybe<Scalars["ID"]>;
  query__models__source__id?: InputMaybe<Scalars["ID"]>;
  query__models__value?: InputMaybe<Scalars["GenericScalar"]>;
  query__models__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  query__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__name__owner__id?: InputMaybe<Scalars["ID"]>;
  query__name__source__id?: InputMaybe<Scalars["ID"]>;
  query__name__value?: InputMaybe<Scalars["String"]>;
  query__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  query__operations__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__operations__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__operations__owner__id?: InputMaybe<Scalars["ID"]>;
  query__operations__source__id?: InputMaybe<Scalars["ID"]>;
  query__operations__value?: InputMaybe<Scalars["GenericScalar"]>;
  query__operations__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  query__query__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__query__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__query__owner__id?: InputMaybe<Scalars["ID"]>;
  query__query__source__id?: InputMaybe<Scalars["ID"]>;
  query__query__value?: InputMaybe<Scalars["String"]>;
  query__query__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  query__variables__is_protected?: InputMaybe<Scalars["Boolean"]>;
  query__variables__is_visible?: InputMaybe<Scalars["Boolean"]>;
  query__variables__owner__id?: InputMaybe<Scalars["ID"]>;
  query__variables__source__id?: InputMaybe<Scalars["ID"]>;
  query__variables__value?: InputMaybe<Scalars["GenericScalar"]>;
  query__variables__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  repository__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__description__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__description__source__id?: InputMaybe<Scalars["ID"]>;
  repository__description__value?: InputMaybe<Scalars["String"]>;
  repository__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  repository__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  repository__location__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__location__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__location__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__location__source__id?: InputMaybe<Scalars["ID"]>;
  repository__location__value?: InputMaybe<Scalars["String"]>;
  repository__location__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  repository__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__name__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__name__source__id?: InputMaybe<Scalars["ID"]>;
  repository__name__value?: InputMaybe<Scalars["String"]>;
  repository__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  repository__password__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__password__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__password__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__password__source__id?: InputMaybe<Scalars["ID"]>;
  repository__password__value?: InputMaybe<Scalars["String"]>;
  repository__password__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  repository__username__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__username__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__username__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__username__source__id?: InputMaybe<Scalars["ID"]>;
  repository__username__value?: InputMaybe<Scalars["String"]>;
  repository__username__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  tags__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  tags__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  tags__description__owner__id?: InputMaybe<Scalars["ID"]>;
  tags__description__source__id?: InputMaybe<Scalars["ID"]>;
  tags__description__value?: InputMaybe<Scalars["String"]>;
  tags__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  tags__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  tags__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  tags__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  tags__name__owner__id?: InputMaybe<Scalars["ID"]>;
  tags__name__source__id?: InputMaybe<Scalars["ID"]>;
  tags__name__value?: InputMaybe<Scalars["String"]>;
  tags__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  timeout__is_protected?: InputMaybe<Scalars["Boolean"]>;
  timeout__is_visible?: InputMaybe<Scalars["Boolean"]>;
  timeout__owner__id?: InputMaybe<Scalars["ID"]>;
  timeout__source__id?: InputMaybe<Scalars["ID"]>;
  timeout__value?: InputMaybe<Scalars["Int"]>;
  timeout__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
};

export type QueryCoreUserValidatorArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  check_definition__class_name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  check_definition__class_name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  check_definition__class_name__owner__id?: InputMaybe<Scalars["ID"]>;
  check_definition__class_name__source__id?: InputMaybe<Scalars["ID"]>;
  check_definition__class_name__value?: InputMaybe<Scalars["String"]>;
  check_definition__class_name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  check_definition__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  check_definition__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  check_definition__description__owner__id?: InputMaybe<Scalars["ID"]>;
  check_definition__description__source__id?: InputMaybe<Scalars["ID"]>;
  check_definition__description__value?: InputMaybe<Scalars["String"]>;
  check_definition__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  check_definition__file_path__is_protected?: InputMaybe<Scalars["Boolean"]>;
  check_definition__file_path__is_visible?: InputMaybe<Scalars["Boolean"]>;
  check_definition__file_path__owner__id?: InputMaybe<Scalars["ID"]>;
  check_definition__file_path__source__id?: InputMaybe<Scalars["ID"]>;
  check_definition__file_path__value?: InputMaybe<Scalars["String"]>;
  check_definition__file_path__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  check_definition__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  check_definition__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  check_definition__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  check_definition__name__owner__id?: InputMaybe<Scalars["ID"]>;
  check_definition__name__source__id?: InputMaybe<Scalars["ID"]>;
  check_definition__name__value?: InputMaybe<Scalars["String"]>;
  check_definition__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  check_definition__parameters__is_protected?: InputMaybe<Scalars["Boolean"]>;
  check_definition__parameters__is_visible?: InputMaybe<Scalars["Boolean"]>;
  check_definition__parameters__owner__id?: InputMaybe<Scalars["ID"]>;
  check_definition__parameters__source__id?: InputMaybe<Scalars["ID"]>;
  check_definition__parameters__value?: InputMaybe<Scalars["GenericScalar"]>;
  check_definition__parameters__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  check_definition__timeout__is_protected?: InputMaybe<Scalars["Boolean"]>;
  check_definition__timeout__is_visible?: InputMaybe<Scalars["Boolean"]>;
  check_definition__timeout__owner__id?: InputMaybe<Scalars["ID"]>;
  check_definition__timeout__source__id?: InputMaybe<Scalars["ID"]>;
  check_definition__timeout__value?: InputMaybe<Scalars["Int"]>;
  check_definition__timeout__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  checks__conclusion__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__conclusion__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__conclusion__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__conclusion__source__id?: InputMaybe<Scalars["ID"]>;
  checks__conclusion__value?: InputMaybe<Scalars["String"]>;
  checks__conclusion__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__created_at__source__id?: InputMaybe<Scalars["ID"]>;
  checks__created_at__value?: InputMaybe<Scalars["String"]>;
  checks__created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  checks__kind__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__kind__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__kind__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__kind__source__id?: InputMaybe<Scalars["ID"]>;
  checks__kind__value?: InputMaybe<Scalars["String"]>;
  checks__kind__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__label__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__label__source__id?: InputMaybe<Scalars["ID"]>;
  checks__label__value?: InputMaybe<Scalars["String"]>;
  checks__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__message__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__message__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__message__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__message__source__id?: InputMaybe<Scalars["ID"]>;
  checks__message__value?: InputMaybe<Scalars["String"]>;
  checks__message__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__name__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__name__source__id?: InputMaybe<Scalars["ID"]>;
  checks__name__value?: InputMaybe<Scalars["String"]>;
  checks__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__origin__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__origin__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__origin__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__origin__source__id?: InputMaybe<Scalars["ID"]>;
  checks__origin__value?: InputMaybe<Scalars["String"]>;
  checks__origin__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__severity__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__severity__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__severity__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__severity__source__id?: InputMaybe<Scalars["ID"]>;
  checks__severity__value?: InputMaybe<Scalars["String"]>;
  checks__severity__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  completed_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  completed_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  completed_at__owner__id?: InputMaybe<Scalars["ID"]>;
  completed_at__source__id?: InputMaybe<Scalars["ID"]>;
  completed_at__value?: InputMaybe<Scalars["String"]>;
  completed_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  conclusion__is_protected?: InputMaybe<Scalars["Boolean"]>;
  conclusion__is_visible?: InputMaybe<Scalars["Boolean"]>;
  conclusion__owner__id?: InputMaybe<Scalars["ID"]>;
  conclusion__source__id?: InputMaybe<Scalars["ID"]>;
  conclusion__value?: InputMaybe<Scalars["String"]>;
  conclusion__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__description__owner__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__description__source__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__description__value?: InputMaybe<Scalars["String"]>;
  proposed_change__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  proposed_change__destination_branch__is_protected?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__destination_branch__is_visible?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__destination_branch__owner__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__destination_branch__source__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__destination_branch__value?: InputMaybe<Scalars["String"]>;
  proposed_change__destination_branch__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  proposed_change__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  proposed_change__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__name__owner__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__name__source__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__name__value?: InputMaybe<Scalars["String"]>;
  proposed_change__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  proposed_change__source_branch__is_protected?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__source_branch__is_visible?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__source_branch__owner__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__source_branch__source__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__source_branch__value?: InputMaybe<Scalars["String"]>;
  proposed_change__source_branch__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  proposed_change__state__is_protected?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__state__is_visible?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__state__owner__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__state__source__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__state__value?: InputMaybe<Scalars["String"]>;
  proposed_change__state__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  repository__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__description__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__description__source__id?: InputMaybe<Scalars["ID"]>;
  repository__description__value?: InputMaybe<Scalars["String"]>;
  repository__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  repository__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  repository__location__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__location__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__location__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__location__source__id?: InputMaybe<Scalars["ID"]>;
  repository__location__value?: InputMaybe<Scalars["String"]>;
  repository__location__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  repository__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__name__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__name__source__id?: InputMaybe<Scalars["ID"]>;
  repository__name__value?: InputMaybe<Scalars["String"]>;
  repository__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  repository__password__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__password__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__password__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__password__source__id?: InputMaybe<Scalars["ID"]>;
  repository__password__value?: InputMaybe<Scalars["String"]>;
  repository__password__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  repository__username__is_protected?: InputMaybe<Scalars["Boolean"]>;
  repository__username__is_visible?: InputMaybe<Scalars["Boolean"]>;
  repository__username__owner__id?: InputMaybe<Scalars["ID"]>;
  repository__username__source__id?: InputMaybe<Scalars["ID"]>;
  repository__username__value?: InputMaybe<Scalars["String"]>;
  repository__username__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  started_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  started_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  started_at__owner__id?: InputMaybe<Scalars["ID"]>;
  started_at__source__id?: InputMaybe<Scalars["ID"]>;
  started_at__value?: InputMaybe<Scalars["String"]>;
  started_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  state__is_protected?: InputMaybe<Scalars["Boolean"]>;
  state__is_visible?: InputMaybe<Scalars["Boolean"]>;
  state__owner__id?: InputMaybe<Scalars["ID"]>;
  state__source__id?: InputMaybe<Scalars["ID"]>;
  state__value?: InputMaybe<Scalars["String"]>;
  state__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryCoreValidatorArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__conclusion__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__conclusion__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__conclusion__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__conclusion__source__id?: InputMaybe<Scalars["ID"]>;
  checks__conclusion__value?: InputMaybe<Scalars["String"]>;
  checks__conclusion__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__created_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__created_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__created_at__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__created_at__source__id?: InputMaybe<Scalars["ID"]>;
  checks__created_at__value?: InputMaybe<Scalars["String"]>;
  checks__created_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  checks__kind__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__kind__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__kind__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__kind__source__id?: InputMaybe<Scalars["ID"]>;
  checks__kind__value?: InputMaybe<Scalars["String"]>;
  checks__kind__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__label__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__label__source__id?: InputMaybe<Scalars["ID"]>;
  checks__label__value?: InputMaybe<Scalars["String"]>;
  checks__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__message__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__message__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__message__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__message__source__id?: InputMaybe<Scalars["ID"]>;
  checks__message__value?: InputMaybe<Scalars["String"]>;
  checks__message__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__name__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__name__source__id?: InputMaybe<Scalars["ID"]>;
  checks__name__value?: InputMaybe<Scalars["String"]>;
  checks__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__origin__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__origin__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__origin__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__origin__source__id?: InputMaybe<Scalars["ID"]>;
  checks__origin__value?: InputMaybe<Scalars["String"]>;
  checks__origin__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  checks__severity__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checks__severity__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checks__severity__owner__id?: InputMaybe<Scalars["ID"]>;
  checks__severity__source__id?: InputMaybe<Scalars["ID"]>;
  checks__severity__value?: InputMaybe<Scalars["String"]>;
  checks__severity__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  completed_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  completed_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  completed_at__owner__id?: InputMaybe<Scalars["ID"]>;
  completed_at__source__id?: InputMaybe<Scalars["ID"]>;
  completed_at__value?: InputMaybe<Scalars["String"]>;
  completed_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  conclusion__is_protected?: InputMaybe<Scalars["Boolean"]>;
  conclusion__is_visible?: InputMaybe<Scalars["Boolean"]>;
  conclusion__owner__id?: InputMaybe<Scalars["ID"]>;
  conclusion__source__id?: InputMaybe<Scalars["ID"]>;
  conclusion__value?: InputMaybe<Scalars["String"]>;
  conclusion__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__description__owner__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__description__source__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__description__value?: InputMaybe<Scalars["String"]>;
  proposed_change__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  proposed_change__destination_branch__is_protected?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__destination_branch__is_visible?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__destination_branch__owner__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__destination_branch__source__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__destination_branch__value?: InputMaybe<Scalars["String"]>;
  proposed_change__destination_branch__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  proposed_change__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  proposed_change__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__name__owner__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__name__source__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__name__value?: InputMaybe<Scalars["String"]>;
  proposed_change__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  proposed_change__source_branch__is_protected?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__source_branch__is_visible?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__source_branch__owner__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__source_branch__source__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__source_branch__value?: InputMaybe<Scalars["String"]>;
  proposed_change__source_branch__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  proposed_change__state__is_protected?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__state__is_visible?: InputMaybe<Scalars["Boolean"]>;
  proposed_change__state__owner__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__state__source__id?: InputMaybe<Scalars["ID"]>;
  proposed_change__state__value?: InputMaybe<Scalars["String"]>;
  proposed_change__state__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  started_at__is_protected?: InputMaybe<Scalars["Boolean"]>;
  started_at__is_visible?: InputMaybe<Scalars["Boolean"]>;
  started_at__owner__id?: InputMaybe<Scalars["ID"]>;
  started_at__source__id?: InputMaybe<Scalars["ID"]>;
  started_at__value?: InputMaybe<Scalars["String"]>;
  started_at__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  state__is_protected?: InputMaybe<Scalars["Boolean"]>;
  state__is_visible?: InputMaybe<Scalars["Boolean"]>;
  state__owner__id?: InputMaybe<Scalars["ID"]>;
  state__source__id?: InputMaybe<Scalars["ID"]>;
  state__value?: InputMaybe<Scalars["String"]>;
  state__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryCoreWebhookArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  url__is_protected?: InputMaybe<Scalars["Boolean"]>;
  url__is_visible?: InputMaybe<Scalars["Boolean"]>;
  url__owner__id?: InputMaybe<Scalars["ID"]>;
  url__source__id?: InputMaybe<Scalars["ID"]>;
  url__value?: InputMaybe<Scalars["String"]>;
  url__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  validate_certificates__is_protected?: InputMaybe<Scalars["Boolean"]>;
  validate_certificates__is_visible?: InputMaybe<Scalars["Boolean"]>;
  validate_certificates__owner__id?: InputMaybe<Scalars["ID"]>;
  validate_certificates__source__id?: InputMaybe<Scalars["ID"]>;
  validate_certificates__value?: InputMaybe<Scalars["Boolean"]>;
  validate_certificates__values?: InputMaybe<Array<InputMaybe<Scalars["Boolean"]>>>;
};

export type QueryDemoEdgeFabricArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  nbr_racks__is_protected?: InputMaybe<Scalars["Boolean"]>;
  nbr_racks__is_visible?: InputMaybe<Scalars["Boolean"]>;
  nbr_racks__owner__id?: InputMaybe<Scalars["ID"]>;
  nbr_racks__source__id?: InputMaybe<Scalars["ID"]>;
  nbr_racks__value?: InputMaybe<Scalars["Int"]>;
  nbr_racks__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  tags__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  tags__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  tags__description__owner__id?: InputMaybe<Scalars["ID"]>;
  tags__description__source__id?: InputMaybe<Scalars["ID"]>;
  tags__description__value?: InputMaybe<Scalars["String"]>;
  tags__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  tags__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  tags__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  tags__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  tags__name__owner__id?: InputMaybe<Scalars["ID"]>;
  tags__name__source__id?: InputMaybe<Scalars["ID"]>;
  tags__name__value?: InputMaybe<Scalars["String"]>;
  tags__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryDiffSummaryArgs = {
  branch_only?: InputMaybe<Scalars["Boolean"]>;
  time_from?: InputMaybe<Scalars["String"]>;
  time_to?: InputMaybe<Scalars["String"]>;
};

export type QueryDiffSummaryOldArgs = {
  branch_only?: InputMaybe<Scalars["Boolean"]>;
  time_from?: InputMaybe<Scalars["String"]>;
  time_to?: InputMaybe<Scalars["String"]>;
};

export type QueryInfraAutonomousSystemArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  asn__is_protected?: InputMaybe<Scalars["Boolean"]>;
  asn__is_visible?: InputMaybe<Scalars["Boolean"]>;
  asn__owner__id?: InputMaybe<Scalars["ID"]>;
  asn__source__id?: InputMaybe<Scalars["ID"]>;
  asn__value?: InputMaybe<Scalars["Int"]>;
  asn__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  organization__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  organization__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  organization__description__owner__id?: InputMaybe<Scalars["ID"]>;
  organization__description__source__id?: InputMaybe<Scalars["ID"]>;
  organization__description__value?: InputMaybe<Scalars["String"]>;
  organization__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  organization__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  organization__label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  organization__label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  organization__label__owner__id?: InputMaybe<Scalars["ID"]>;
  organization__label__source__id?: InputMaybe<Scalars["ID"]>;
  organization__label__value?: InputMaybe<Scalars["String"]>;
  organization__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  organization__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  organization__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  organization__name__owner__id?: InputMaybe<Scalars["ID"]>;
  organization__name__source__id?: InputMaybe<Scalars["ID"]>;
  organization__name__value?: InputMaybe<Scalars["String"]>;
  organization__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryInfraBgpPeerGroupArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  export_policies__is_protected?: InputMaybe<Scalars["Boolean"]>;
  export_policies__is_visible?: InputMaybe<Scalars["Boolean"]>;
  export_policies__owner__id?: InputMaybe<Scalars["ID"]>;
  export_policies__source__id?: InputMaybe<Scalars["ID"]>;
  export_policies__value?: InputMaybe<Scalars["String"]>;
  export_policies__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  import_policies__is_protected?: InputMaybe<Scalars["Boolean"]>;
  import_policies__is_visible?: InputMaybe<Scalars["Boolean"]>;
  import_policies__owner__id?: InputMaybe<Scalars["ID"]>;
  import_policies__source__id?: InputMaybe<Scalars["ID"]>;
  import_policies__value?: InputMaybe<Scalars["String"]>;
  import_policies__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  local_as__asn__is_protected?: InputMaybe<Scalars["Boolean"]>;
  local_as__asn__is_visible?: InputMaybe<Scalars["Boolean"]>;
  local_as__asn__owner__id?: InputMaybe<Scalars["ID"]>;
  local_as__asn__source__id?: InputMaybe<Scalars["ID"]>;
  local_as__asn__value?: InputMaybe<Scalars["Int"]>;
  local_as__asn__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  local_as__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  local_as__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  local_as__description__owner__id?: InputMaybe<Scalars["ID"]>;
  local_as__description__source__id?: InputMaybe<Scalars["ID"]>;
  local_as__description__value?: InputMaybe<Scalars["String"]>;
  local_as__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  local_as__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  local_as__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  local_as__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  local_as__name__owner__id?: InputMaybe<Scalars["ID"]>;
  local_as__name__source__id?: InputMaybe<Scalars["ID"]>;
  local_as__name__value?: InputMaybe<Scalars["String"]>;
  local_as__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  remote_as__asn__is_protected?: InputMaybe<Scalars["Boolean"]>;
  remote_as__asn__is_visible?: InputMaybe<Scalars["Boolean"]>;
  remote_as__asn__owner__id?: InputMaybe<Scalars["ID"]>;
  remote_as__asn__source__id?: InputMaybe<Scalars["ID"]>;
  remote_as__asn__value?: InputMaybe<Scalars["Int"]>;
  remote_as__asn__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  remote_as__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  remote_as__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  remote_as__description__owner__id?: InputMaybe<Scalars["ID"]>;
  remote_as__description__source__id?: InputMaybe<Scalars["ID"]>;
  remote_as__description__value?: InputMaybe<Scalars["String"]>;
  remote_as__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  remote_as__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  remote_as__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  remote_as__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  remote_as__name__owner__id?: InputMaybe<Scalars["ID"]>;
  remote_as__name__source__id?: InputMaybe<Scalars["ID"]>;
  remote_as__name__value?: InputMaybe<Scalars["String"]>;
  remote_as__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryInfraBgpSessionArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  artifacts__checksum__is_protected?: InputMaybe<Scalars["Boolean"]>;
  artifacts__checksum__is_visible?: InputMaybe<Scalars["Boolean"]>;
  artifacts__checksum__owner__id?: InputMaybe<Scalars["ID"]>;
  artifacts__checksum__source__id?: InputMaybe<Scalars["ID"]>;
  artifacts__checksum__value?: InputMaybe<Scalars["String"]>;
  artifacts__checksum__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  artifacts__content_type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  artifacts__content_type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  artifacts__content_type__owner__id?: InputMaybe<Scalars["ID"]>;
  artifacts__content_type__source__id?: InputMaybe<Scalars["ID"]>;
  artifacts__content_type__value?: InputMaybe<Scalars["String"]>;
  artifacts__content_type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  artifacts__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  artifacts__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  artifacts__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  artifacts__name__owner__id?: InputMaybe<Scalars["ID"]>;
  artifacts__name__source__id?: InputMaybe<Scalars["ID"]>;
  artifacts__name__value?: InputMaybe<Scalars["String"]>;
  artifacts__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  artifacts__parameters__is_protected?: InputMaybe<Scalars["Boolean"]>;
  artifacts__parameters__is_visible?: InputMaybe<Scalars["Boolean"]>;
  artifacts__parameters__owner__id?: InputMaybe<Scalars["ID"]>;
  artifacts__parameters__source__id?: InputMaybe<Scalars["ID"]>;
  artifacts__parameters__value?: InputMaybe<Scalars["GenericScalar"]>;
  artifacts__parameters__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  artifacts__status__is_protected?: InputMaybe<Scalars["Boolean"]>;
  artifacts__status__is_visible?: InputMaybe<Scalars["Boolean"]>;
  artifacts__status__owner__id?: InputMaybe<Scalars["ID"]>;
  artifacts__status__source__id?: InputMaybe<Scalars["ID"]>;
  artifacts__status__value?: InputMaybe<Scalars["String"]>;
  artifacts__status__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  artifacts__storage_id__is_protected?: InputMaybe<Scalars["Boolean"]>;
  artifacts__storage_id__is_visible?: InputMaybe<Scalars["Boolean"]>;
  artifacts__storage_id__owner__id?: InputMaybe<Scalars["ID"]>;
  artifacts__storage_id__source__id?: InputMaybe<Scalars["ID"]>;
  artifacts__storage_id__value?: InputMaybe<Scalars["String"]>;
  artifacts__storage_id__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  device__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  device__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  device__description__owner__id?: InputMaybe<Scalars["ID"]>;
  device__description__source__id?: InputMaybe<Scalars["ID"]>;
  device__description__value?: InputMaybe<Scalars["String"]>;
  device__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  device__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  device__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  device__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  device__name__owner__id?: InputMaybe<Scalars["ID"]>;
  device__name__source__id?: InputMaybe<Scalars["ID"]>;
  device__name__value?: InputMaybe<Scalars["String"]>;
  device__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  device__role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  device__role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  device__role__owner__id?: InputMaybe<Scalars["ID"]>;
  device__role__source__id?: InputMaybe<Scalars["ID"]>;
  device__role__value?: InputMaybe<Scalars["String"]>;
  device__role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  device__status__is_protected?: InputMaybe<Scalars["Boolean"]>;
  device__status__is_visible?: InputMaybe<Scalars["Boolean"]>;
  device__status__owner__id?: InputMaybe<Scalars["ID"]>;
  device__status__source__id?: InputMaybe<Scalars["ID"]>;
  device__status__value?: InputMaybe<Scalars["String"]>;
  device__status__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  device__type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  device__type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  device__type__owner__id?: InputMaybe<Scalars["ID"]>;
  device__type__source__id?: InputMaybe<Scalars["ID"]>;
  device__type__value?: InputMaybe<Scalars["String"]>;
  device__type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  export_policies__is_protected?: InputMaybe<Scalars["Boolean"]>;
  export_policies__is_visible?: InputMaybe<Scalars["Boolean"]>;
  export_policies__owner__id?: InputMaybe<Scalars["ID"]>;
  export_policies__source__id?: InputMaybe<Scalars["ID"]>;
  export_policies__value?: InputMaybe<Scalars["String"]>;
  export_policies__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  import_policies__is_protected?: InputMaybe<Scalars["Boolean"]>;
  import_policies__is_visible?: InputMaybe<Scalars["Boolean"]>;
  import_policies__owner__id?: InputMaybe<Scalars["ID"]>;
  import_policies__source__id?: InputMaybe<Scalars["ID"]>;
  import_policies__value?: InputMaybe<Scalars["String"]>;
  import_policies__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  local_as__asn__is_protected?: InputMaybe<Scalars["Boolean"]>;
  local_as__asn__is_visible?: InputMaybe<Scalars["Boolean"]>;
  local_as__asn__owner__id?: InputMaybe<Scalars["ID"]>;
  local_as__asn__source__id?: InputMaybe<Scalars["ID"]>;
  local_as__asn__value?: InputMaybe<Scalars["Int"]>;
  local_as__asn__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  local_as__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  local_as__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  local_as__description__owner__id?: InputMaybe<Scalars["ID"]>;
  local_as__description__source__id?: InputMaybe<Scalars["ID"]>;
  local_as__description__value?: InputMaybe<Scalars["String"]>;
  local_as__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  local_as__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  local_as__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  local_as__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  local_as__name__owner__id?: InputMaybe<Scalars["ID"]>;
  local_as__name__source__id?: InputMaybe<Scalars["ID"]>;
  local_as__name__value?: InputMaybe<Scalars["String"]>;
  local_as__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  local_ip__address__is_protected?: InputMaybe<Scalars["Boolean"]>;
  local_ip__address__is_visible?: InputMaybe<Scalars["Boolean"]>;
  local_ip__address__owner__id?: InputMaybe<Scalars["ID"]>;
  local_ip__address__source__id?: InputMaybe<Scalars["ID"]>;
  local_ip__address__value?: InputMaybe<Scalars["String"]>;
  local_ip__address__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  local_ip__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  local_ip__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  local_ip__description__owner__id?: InputMaybe<Scalars["ID"]>;
  local_ip__description__source__id?: InputMaybe<Scalars["ID"]>;
  local_ip__description__value?: InputMaybe<Scalars["String"]>;
  local_ip__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  local_ip__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  peer_group__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  peer_group__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  peer_group__description__owner__id?: InputMaybe<Scalars["ID"]>;
  peer_group__description__source__id?: InputMaybe<Scalars["ID"]>;
  peer_group__description__value?: InputMaybe<Scalars["String"]>;
  peer_group__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  peer_group__export_policies__is_protected?: InputMaybe<Scalars["Boolean"]>;
  peer_group__export_policies__is_visible?: InputMaybe<Scalars["Boolean"]>;
  peer_group__export_policies__owner__id?: InputMaybe<Scalars["ID"]>;
  peer_group__export_policies__source__id?: InputMaybe<Scalars["ID"]>;
  peer_group__export_policies__value?: InputMaybe<Scalars["String"]>;
  peer_group__export_policies__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  peer_group__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  peer_group__import_policies__is_protected?: InputMaybe<Scalars["Boolean"]>;
  peer_group__import_policies__is_visible?: InputMaybe<Scalars["Boolean"]>;
  peer_group__import_policies__owner__id?: InputMaybe<Scalars["ID"]>;
  peer_group__import_policies__source__id?: InputMaybe<Scalars["ID"]>;
  peer_group__import_policies__value?: InputMaybe<Scalars["String"]>;
  peer_group__import_policies__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  peer_group__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  peer_group__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  peer_group__name__owner__id?: InputMaybe<Scalars["ID"]>;
  peer_group__name__source__id?: InputMaybe<Scalars["ID"]>;
  peer_group__name__value?: InputMaybe<Scalars["String"]>;
  peer_group__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  peer_session__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  peer_session__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  peer_session__description__owner__id?: InputMaybe<Scalars["ID"]>;
  peer_session__description__source__id?: InputMaybe<Scalars["ID"]>;
  peer_session__description__value?: InputMaybe<Scalars["String"]>;
  peer_session__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  peer_session__export_policies__is_protected?: InputMaybe<Scalars["Boolean"]>;
  peer_session__export_policies__is_visible?: InputMaybe<Scalars["Boolean"]>;
  peer_session__export_policies__owner__id?: InputMaybe<Scalars["ID"]>;
  peer_session__export_policies__source__id?: InputMaybe<Scalars["ID"]>;
  peer_session__export_policies__value?: InputMaybe<Scalars["String"]>;
  peer_session__export_policies__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  peer_session__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  peer_session__import_policies__is_protected?: InputMaybe<Scalars["Boolean"]>;
  peer_session__import_policies__is_visible?: InputMaybe<Scalars["Boolean"]>;
  peer_session__import_policies__owner__id?: InputMaybe<Scalars["ID"]>;
  peer_session__import_policies__source__id?: InputMaybe<Scalars["ID"]>;
  peer_session__import_policies__value?: InputMaybe<Scalars["String"]>;
  peer_session__import_policies__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  peer_session__role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  peer_session__role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  peer_session__role__owner__id?: InputMaybe<Scalars["ID"]>;
  peer_session__role__source__id?: InputMaybe<Scalars["ID"]>;
  peer_session__role__value?: InputMaybe<Scalars["String"]>;
  peer_session__role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  peer_session__status__is_protected?: InputMaybe<Scalars["Boolean"]>;
  peer_session__status__is_visible?: InputMaybe<Scalars["Boolean"]>;
  peer_session__status__owner__id?: InputMaybe<Scalars["ID"]>;
  peer_session__status__source__id?: InputMaybe<Scalars["ID"]>;
  peer_session__status__value?: InputMaybe<Scalars["String"]>;
  peer_session__status__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  peer_session__type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  peer_session__type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  peer_session__type__owner__id?: InputMaybe<Scalars["ID"]>;
  peer_session__type__source__id?: InputMaybe<Scalars["ID"]>;
  peer_session__type__value?: InputMaybe<Scalars["String"]>;
  peer_session__type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  remote_as__asn__is_protected?: InputMaybe<Scalars["Boolean"]>;
  remote_as__asn__is_visible?: InputMaybe<Scalars["Boolean"]>;
  remote_as__asn__owner__id?: InputMaybe<Scalars["ID"]>;
  remote_as__asn__source__id?: InputMaybe<Scalars["ID"]>;
  remote_as__asn__value?: InputMaybe<Scalars["Int"]>;
  remote_as__asn__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  remote_as__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  remote_as__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  remote_as__description__owner__id?: InputMaybe<Scalars["ID"]>;
  remote_as__description__source__id?: InputMaybe<Scalars["ID"]>;
  remote_as__description__value?: InputMaybe<Scalars["String"]>;
  remote_as__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  remote_as__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  remote_as__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  remote_as__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  remote_as__name__owner__id?: InputMaybe<Scalars["ID"]>;
  remote_as__name__source__id?: InputMaybe<Scalars["ID"]>;
  remote_as__name__value?: InputMaybe<Scalars["String"]>;
  remote_as__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  remote_ip__address__is_protected?: InputMaybe<Scalars["Boolean"]>;
  remote_ip__address__is_visible?: InputMaybe<Scalars["Boolean"]>;
  remote_ip__address__owner__id?: InputMaybe<Scalars["ID"]>;
  remote_ip__address__source__id?: InputMaybe<Scalars["ID"]>;
  remote_ip__address__value?: InputMaybe<Scalars["String"]>;
  remote_ip__address__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  remote_ip__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  remote_ip__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  remote_ip__description__owner__id?: InputMaybe<Scalars["ID"]>;
  remote_ip__description__source__id?: InputMaybe<Scalars["ID"]>;
  remote_ip__description__value?: InputMaybe<Scalars["String"]>;
  remote_ip__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  remote_ip__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  role__owner__id?: InputMaybe<Scalars["ID"]>;
  role__source__id?: InputMaybe<Scalars["ID"]>;
  role__value?: InputMaybe<Scalars["String"]>;
  role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  status__is_protected?: InputMaybe<Scalars["Boolean"]>;
  status__is_visible?: InputMaybe<Scalars["Boolean"]>;
  status__owner__id?: InputMaybe<Scalars["ID"]>;
  status__source__id?: InputMaybe<Scalars["ID"]>;
  status__value?: InputMaybe<Scalars["String"]>;
  status__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  type__owner__id?: InputMaybe<Scalars["ID"]>;
  type__source__id?: InputMaybe<Scalars["ID"]>;
  type__value?: InputMaybe<Scalars["String"]>;
  type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryInfraCircuitArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  circuit_id__is_protected?: InputMaybe<Scalars["Boolean"]>;
  circuit_id__is_visible?: InputMaybe<Scalars["Boolean"]>;
  circuit_id__owner__id?: InputMaybe<Scalars["ID"]>;
  circuit_id__source__id?: InputMaybe<Scalars["ID"]>;
  circuit_id__value?: InputMaybe<Scalars["String"]>;
  circuit_id__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  endpoints__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  endpoints__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  endpoints__description__owner__id?: InputMaybe<Scalars["ID"]>;
  endpoints__description__source__id?: InputMaybe<Scalars["ID"]>;
  endpoints__description__value?: InputMaybe<Scalars["String"]>;
  endpoints__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  endpoints__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  provider__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  provider__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  provider__description__owner__id?: InputMaybe<Scalars["ID"]>;
  provider__description__source__id?: InputMaybe<Scalars["ID"]>;
  provider__description__value?: InputMaybe<Scalars["String"]>;
  provider__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  provider__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  provider__label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  provider__label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  provider__label__owner__id?: InputMaybe<Scalars["ID"]>;
  provider__label__source__id?: InputMaybe<Scalars["ID"]>;
  provider__label__value?: InputMaybe<Scalars["String"]>;
  provider__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  provider__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  provider__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  provider__name__owner__id?: InputMaybe<Scalars["ID"]>;
  provider__name__source__id?: InputMaybe<Scalars["ID"]>;
  provider__name__value?: InputMaybe<Scalars["String"]>;
  provider__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  role__owner__id?: InputMaybe<Scalars["ID"]>;
  role__source__id?: InputMaybe<Scalars["ID"]>;
  role__value?: InputMaybe<Scalars["String"]>;
  role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  status__is_protected?: InputMaybe<Scalars["Boolean"]>;
  status__is_visible?: InputMaybe<Scalars["Boolean"]>;
  status__owner__id?: InputMaybe<Scalars["ID"]>;
  status__source__id?: InputMaybe<Scalars["ID"]>;
  status__value?: InputMaybe<Scalars["String"]>;
  status__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  vendor_id__is_protected?: InputMaybe<Scalars["Boolean"]>;
  vendor_id__is_visible?: InputMaybe<Scalars["Boolean"]>;
  vendor_id__owner__id?: InputMaybe<Scalars["ID"]>;
  vendor_id__source__id?: InputMaybe<Scalars["ID"]>;
  vendor_id__value?: InputMaybe<Scalars["String"]>;
  vendor_id__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryInfraCircuitEndpointArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  circuit__circuit_id__is_protected?: InputMaybe<Scalars["Boolean"]>;
  circuit__circuit_id__is_visible?: InputMaybe<Scalars["Boolean"]>;
  circuit__circuit_id__owner__id?: InputMaybe<Scalars["ID"]>;
  circuit__circuit_id__source__id?: InputMaybe<Scalars["ID"]>;
  circuit__circuit_id__value?: InputMaybe<Scalars["String"]>;
  circuit__circuit_id__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  circuit__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  circuit__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  circuit__description__owner__id?: InputMaybe<Scalars["ID"]>;
  circuit__description__source__id?: InputMaybe<Scalars["ID"]>;
  circuit__description__value?: InputMaybe<Scalars["String"]>;
  circuit__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  circuit__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  circuit__role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  circuit__role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  circuit__role__owner__id?: InputMaybe<Scalars["ID"]>;
  circuit__role__source__id?: InputMaybe<Scalars["ID"]>;
  circuit__role__value?: InputMaybe<Scalars["String"]>;
  circuit__role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  circuit__status__is_protected?: InputMaybe<Scalars["Boolean"]>;
  circuit__status__is_visible?: InputMaybe<Scalars["Boolean"]>;
  circuit__status__owner__id?: InputMaybe<Scalars["ID"]>;
  circuit__status__source__id?: InputMaybe<Scalars["ID"]>;
  circuit__status__value?: InputMaybe<Scalars["String"]>;
  circuit__status__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  circuit__vendor_id__is_protected?: InputMaybe<Scalars["Boolean"]>;
  circuit__vendor_id__is_visible?: InputMaybe<Scalars["Boolean"]>;
  circuit__vendor_id__owner__id?: InputMaybe<Scalars["ID"]>;
  circuit__vendor_id__source__id?: InputMaybe<Scalars["ID"]>;
  circuit__vendor_id__value?: InputMaybe<Scalars["String"]>;
  circuit__vendor_id__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  connected_endpoint__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  site__address__is_protected?: InputMaybe<Scalars["Boolean"]>;
  site__address__is_visible?: InputMaybe<Scalars["Boolean"]>;
  site__address__owner__id?: InputMaybe<Scalars["ID"]>;
  site__address__source__id?: InputMaybe<Scalars["ID"]>;
  site__address__value?: InputMaybe<Scalars["String"]>;
  site__address__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  site__city__is_protected?: InputMaybe<Scalars["Boolean"]>;
  site__city__is_visible?: InputMaybe<Scalars["Boolean"]>;
  site__city__owner__id?: InputMaybe<Scalars["ID"]>;
  site__city__source__id?: InputMaybe<Scalars["ID"]>;
  site__city__value?: InputMaybe<Scalars["String"]>;
  site__city__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  site__contact__is_protected?: InputMaybe<Scalars["Boolean"]>;
  site__contact__is_visible?: InputMaybe<Scalars["Boolean"]>;
  site__contact__owner__id?: InputMaybe<Scalars["ID"]>;
  site__contact__source__id?: InputMaybe<Scalars["ID"]>;
  site__contact__value?: InputMaybe<Scalars["String"]>;
  site__contact__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  site__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  site__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  site__description__owner__id?: InputMaybe<Scalars["ID"]>;
  site__description__source__id?: InputMaybe<Scalars["ID"]>;
  site__description__value?: InputMaybe<Scalars["String"]>;
  site__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  site__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  site__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  site__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  site__name__owner__id?: InputMaybe<Scalars["ID"]>;
  site__name__source__id?: InputMaybe<Scalars["ID"]>;
  site__name__value?: InputMaybe<Scalars["String"]>;
  site__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryInfraContinentArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  children__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  children__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  children__description__owner__id?: InputMaybe<Scalars["ID"]>;
  children__description__source__id?: InputMaybe<Scalars["ID"]>;
  children__description__value?: InputMaybe<Scalars["String"]>;
  children__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  children__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  children__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  children__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  children__name__owner__id?: InputMaybe<Scalars["ID"]>;
  children__name__source__id?: InputMaybe<Scalars["ID"]>;
  children__name__value?: InputMaybe<Scalars["String"]>;
  children__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryInfraCountryArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  children__address__is_protected?: InputMaybe<Scalars["Boolean"]>;
  children__address__is_visible?: InputMaybe<Scalars["Boolean"]>;
  children__address__owner__id?: InputMaybe<Scalars["ID"]>;
  children__address__source__id?: InputMaybe<Scalars["ID"]>;
  children__address__value?: InputMaybe<Scalars["String"]>;
  children__address__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  children__city__is_protected?: InputMaybe<Scalars["Boolean"]>;
  children__city__is_visible?: InputMaybe<Scalars["Boolean"]>;
  children__city__owner__id?: InputMaybe<Scalars["ID"]>;
  children__city__source__id?: InputMaybe<Scalars["ID"]>;
  children__city__value?: InputMaybe<Scalars["String"]>;
  children__city__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  children__contact__is_protected?: InputMaybe<Scalars["Boolean"]>;
  children__contact__is_visible?: InputMaybe<Scalars["Boolean"]>;
  children__contact__owner__id?: InputMaybe<Scalars["ID"]>;
  children__contact__source__id?: InputMaybe<Scalars["ID"]>;
  children__contact__value?: InputMaybe<Scalars["String"]>;
  children__contact__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  children__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  children__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  children__description__owner__id?: InputMaybe<Scalars["ID"]>;
  children__description__source__id?: InputMaybe<Scalars["ID"]>;
  children__description__value?: InputMaybe<Scalars["String"]>;
  children__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  children__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  children__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  children__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  children__name__owner__id?: InputMaybe<Scalars["ID"]>;
  children__name__source__id?: InputMaybe<Scalars["ID"]>;
  children__name__value?: InputMaybe<Scalars["String"]>;
  children__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  parent__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  parent__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  parent__description__owner__id?: InputMaybe<Scalars["ID"]>;
  parent__description__source__id?: InputMaybe<Scalars["ID"]>;
  parent__description__value?: InputMaybe<Scalars["String"]>;
  parent__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  parent__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  parent__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  parent__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  parent__name__owner__id?: InputMaybe<Scalars["ID"]>;
  parent__name__source__id?: InputMaybe<Scalars["ID"]>;
  parent__name__value?: InputMaybe<Scalars["String"]>;
  parent__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryInfraDeviceArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  artifacts__checksum__is_protected?: InputMaybe<Scalars["Boolean"]>;
  artifacts__checksum__is_visible?: InputMaybe<Scalars["Boolean"]>;
  artifacts__checksum__owner__id?: InputMaybe<Scalars["ID"]>;
  artifacts__checksum__source__id?: InputMaybe<Scalars["ID"]>;
  artifacts__checksum__value?: InputMaybe<Scalars["String"]>;
  artifacts__checksum__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  artifacts__content_type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  artifacts__content_type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  artifacts__content_type__owner__id?: InputMaybe<Scalars["ID"]>;
  artifacts__content_type__source__id?: InputMaybe<Scalars["ID"]>;
  artifacts__content_type__value?: InputMaybe<Scalars["String"]>;
  artifacts__content_type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  artifacts__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  artifacts__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  artifacts__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  artifacts__name__owner__id?: InputMaybe<Scalars["ID"]>;
  artifacts__name__source__id?: InputMaybe<Scalars["ID"]>;
  artifacts__name__value?: InputMaybe<Scalars["String"]>;
  artifacts__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  artifacts__parameters__is_protected?: InputMaybe<Scalars["Boolean"]>;
  artifacts__parameters__is_visible?: InputMaybe<Scalars["Boolean"]>;
  artifacts__parameters__owner__id?: InputMaybe<Scalars["ID"]>;
  artifacts__parameters__source__id?: InputMaybe<Scalars["ID"]>;
  artifacts__parameters__value?: InputMaybe<Scalars["GenericScalar"]>;
  artifacts__parameters__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  artifacts__status__is_protected?: InputMaybe<Scalars["Boolean"]>;
  artifacts__status__is_visible?: InputMaybe<Scalars["Boolean"]>;
  artifacts__status__owner__id?: InputMaybe<Scalars["ID"]>;
  artifacts__status__source__id?: InputMaybe<Scalars["ID"]>;
  artifacts__status__value?: InputMaybe<Scalars["String"]>;
  artifacts__status__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  artifacts__storage_id__is_protected?: InputMaybe<Scalars["Boolean"]>;
  artifacts__storage_id__is_visible?: InputMaybe<Scalars["Boolean"]>;
  artifacts__storage_id__owner__id?: InputMaybe<Scalars["ID"]>;
  artifacts__storage_id__source__id?: InputMaybe<Scalars["ID"]>;
  artifacts__storage_id__value?: InputMaybe<Scalars["String"]>;
  artifacts__storage_id__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  asn__asn__is_protected?: InputMaybe<Scalars["Boolean"]>;
  asn__asn__is_visible?: InputMaybe<Scalars["Boolean"]>;
  asn__asn__owner__id?: InputMaybe<Scalars["ID"]>;
  asn__asn__source__id?: InputMaybe<Scalars["ID"]>;
  asn__asn__value?: InputMaybe<Scalars["Int"]>;
  asn__asn__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  asn__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  asn__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  asn__description__owner__id?: InputMaybe<Scalars["ID"]>;
  asn__description__source__id?: InputMaybe<Scalars["ID"]>;
  asn__description__value?: InputMaybe<Scalars["String"]>;
  asn__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  asn__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  asn__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  asn__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  asn__name__owner__id?: InputMaybe<Scalars["ID"]>;
  asn__name__source__id?: InputMaybe<Scalars["ID"]>;
  asn__name__value?: InputMaybe<Scalars["String"]>;
  asn__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  interfaces__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  interfaces__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  interfaces__description__owner__id?: InputMaybe<Scalars["ID"]>;
  interfaces__description__source__id?: InputMaybe<Scalars["ID"]>;
  interfaces__description__value?: InputMaybe<Scalars["String"]>;
  interfaces__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  interfaces__enabled__is_protected?: InputMaybe<Scalars["Boolean"]>;
  interfaces__enabled__is_visible?: InputMaybe<Scalars["Boolean"]>;
  interfaces__enabled__owner__id?: InputMaybe<Scalars["ID"]>;
  interfaces__enabled__source__id?: InputMaybe<Scalars["ID"]>;
  interfaces__enabled__value?: InputMaybe<Scalars["Boolean"]>;
  interfaces__enabled__values?: InputMaybe<Array<InputMaybe<Scalars["Boolean"]>>>;
  interfaces__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  interfaces__mtu__is_protected?: InputMaybe<Scalars["Boolean"]>;
  interfaces__mtu__is_visible?: InputMaybe<Scalars["Boolean"]>;
  interfaces__mtu__owner__id?: InputMaybe<Scalars["ID"]>;
  interfaces__mtu__source__id?: InputMaybe<Scalars["ID"]>;
  interfaces__mtu__value?: InputMaybe<Scalars["Int"]>;
  interfaces__mtu__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  interfaces__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  interfaces__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  interfaces__name__owner__id?: InputMaybe<Scalars["ID"]>;
  interfaces__name__source__id?: InputMaybe<Scalars["ID"]>;
  interfaces__name__value?: InputMaybe<Scalars["String"]>;
  interfaces__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  interfaces__role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  interfaces__role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  interfaces__role__owner__id?: InputMaybe<Scalars["ID"]>;
  interfaces__role__source__id?: InputMaybe<Scalars["ID"]>;
  interfaces__role__value?: InputMaybe<Scalars["String"]>;
  interfaces__role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  interfaces__speed__is_protected?: InputMaybe<Scalars["Boolean"]>;
  interfaces__speed__is_visible?: InputMaybe<Scalars["Boolean"]>;
  interfaces__speed__owner__id?: InputMaybe<Scalars["ID"]>;
  interfaces__speed__source__id?: InputMaybe<Scalars["ID"]>;
  interfaces__speed__value?: InputMaybe<Scalars["Int"]>;
  interfaces__speed__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  interfaces__status__is_protected?: InputMaybe<Scalars["Boolean"]>;
  interfaces__status__is_visible?: InputMaybe<Scalars["Boolean"]>;
  interfaces__status__owner__id?: InputMaybe<Scalars["ID"]>;
  interfaces__status__source__id?: InputMaybe<Scalars["ID"]>;
  interfaces__status__value?: InputMaybe<Scalars["String"]>;
  interfaces__status__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  platform__ansible_network_os__is_protected?: InputMaybe<Scalars["Boolean"]>;
  platform__ansible_network_os__is_visible?: InputMaybe<Scalars["Boolean"]>;
  platform__ansible_network_os__owner__id?: InputMaybe<Scalars["ID"]>;
  platform__ansible_network_os__source__id?: InputMaybe<Scalars["ID"]>;
  platform__ansible_network_os__value?: InputMaybe<Scalars["String"]>;
  platform__ansible_network_os__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  platform__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  platform__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  platform__description__owner__id?: InputMaybe<Scalars["ID"]>;
  platform__description__source__id?: InputMaybe<Scalars["ID"]>;
  platform__description__value?: InputMaybe<Scalars["String"]>;
  platform__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  platform__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  platform__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  platform__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  platform__name__owner__id?: InputMaybe<Scalars["ID"]>;
  platform__name__source__id?: InputMaybe<Scalars["ID"]>;
  platform__name__value?: InputMaybe<Scalars["String"]>;
  platform__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  platform__napalm_driver__is_protected?: InputMaybe<Scalars["Boolean"]>;
  platform__napalm_driver__is_visible?: InputMaybe<Scalars["Boolean"]>;
  platform__napalm_driver__owner__id?: InputMaybe<Scalars["ID"]>;
  platform__napalm_driver__source__id?: InputMaybe<Scalars["ID"]>;
  platform__napalm_driver__value?: InputMaybe<Scalars["String"]>;
  platform__napalm_driver__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  platform__netmiko_device_type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  platform__netmiko_device_type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  platform__netmiko_device_type__owner__id?: InputMaybe<Scalars["ID"]>;
  platform__netmiko_device_type__source__id?: InputMaybe<Scalars["ID"]>;
  platform__netmiko_device_type__value?: InputMaybe<Scalars["String"]>;
  platform__netmiko_device_type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  platform__nornir_platform__is_protected?: InputMaybe<Scalars["Boolean"]>;
  platform__nornir_platform__is_visible?: InputMaybe<Scalars["Boolean"]>;
  platform__nornir_platform__owner__id?: InputMaybe<Scalars["ID"]>;
  platform__nornir_platform__source__id?: InputMaybe<Scalars["ID"]>;
  platform__nornir_platform__value?: InputMaybe<Scalars["String"]>;
  platform__nornir_platform__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  primary_address__address__is_protected?: InputMaybe<Scalars["Boolean"]>;
  primary_address__address__is_visible?: InputMaybe<Scalars["Boolean"]>;
  primary_address__address__owner__id?: InputMaybe<Scalars["ID"]>;
  primary_address__address__source__id?: InputMaybe<Scalars["ID"]>;
  primary_address__address__value?: InputMaybe<Scalars["String"]>;
  primary_address__address__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  primary_address__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  primary_address__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  primary_address__description__owner__id?: InputMaybe<Scalars["ID"]>;
  primary_address__description__source__id?: InputMaybe<Scalars["ID"]>;
  primary_address__description__value?: InputMaybe<Scalars["String"]>;
  primary_address__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  primary_address__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  role__owner__id?: InputMaybe<Scalars["ID"]>;
  role__source__id?: InputMaybe<Scalars["ID"]>;
  role__value?: InputMaybe<Scalars["String"]>;
  role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  site__address__is_protected?: InputMaybe<Scalars["Boolean"]>;
  site__address__is_visible?: InputMaybe<Scalars["Boolean"]>;
  site__address__owner__id?: InputMaybe<Scalars["ID"]>;
  site__address__source__id?: InputMaybe<Scalars["ID"]>;
  site__address__value?: InputMaybe<Scalars["String"]>;
  site__address__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  site__city__is_protected?: InputMaybe<Scalars["Boolean"]>;
  site__city__is_visible?: InputMaybe<Scalars["Boolean"]>;
  site__city__owner__id?: InputMaybe<Scalars["ID"]>;
  site__city__source__id?: InputMaybe<Scalars["ID"]>;
  site__city__value?: InputMaybe<Scalars["String"]>;
  site__city__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  site__contact__is_protected?: InputMaybe<Scalars["Boolean"]>;
  site__contact__is_visible?: InputMaybe<Scalars["Boolean"]>;
  site__contact__owner__id?: InputMaybe<Scalars["ID"]>;
  site__contact__source__id?: InputMaybe<Scalars["ID"]>;
  site__contact__value?: InputMaybe<Scalars["String"]>;
  site__contact__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  site__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  site__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  site__description__owner__id?: InputMaybe<Scalars["ID"]>;
  site__description__source__id?: InputMaybe<Scalars["ID"]>;
  site__description__value?: InputMaybe<Scalars["String"]>;
  site__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  site__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  site__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  site__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  site__name__owner__id?: InputMaybe<Scalars["ID"]>;
  site__name__source__id?: InputMaybe<Scalars["ID"]>;
  site__name__value?: InputMaybe<Scalars["String"]>;
  site__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  status__is_protected?: InputMaybe<Scalars["Boolean"]>;
  status__is_visible?: InputMaybe<Scalars["Boolean"]>;
  status__owner__id?: InputMaybe<Scalars["ID"]>;
  status__source__id?: InputMaybe<Scalars["ID"]>;
  status__value?: InputMaybe<Scalars["String"]>;
  status__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  tags__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  tags__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  tags__description__owner__id?: InputMaybe<Scalars["ID"]>;
  tags__description__source__id?: InputMaybe<Scalars["ID"]>;
  tags__description__value?: InputMaybe<Scalars["String"]>;
  tags__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  tags__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  tags__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  tags__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  tags__name__owner__id?: InputMaybe<Scalars["ID"]>;
  tags__name__source__id?: InputMaybe<Scalars["ID"]>;
  tags__name__value?: InputMaybe<Scalars["String"]>;
  tags__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  type__owner__id?: InputMaybe<Scalars["ID"]>;
  type__source__id?: InputMaybe<Scalars["ID"]>;
  type__value?: InputMaybe<Scalars["String"]>;
  type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryInfraEndpointArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  connected_endpoint__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryInfraIpAddressArgs = {
  address__is_protected?: InputMaybe<Scalars["Boolean"]>;
  address__is_visible?: InputMaybe<Scalars["Boolean"]>;
  address__owner__id?: InputMaybe<Scalars["ID"]>;
  address__source__id?: InputMaybe<Scalars["ID"]>;
  address__value?: InputMaybe<Scalars["String"]>;
  address__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  interface__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  interface__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  interface__description__owner__id?: InputMaybe<Scalars["ID"]>;
  interface__description__source__id?: InputMaybe<Scalars["ID"]>;
  interface__description__value?: InputMaybe<Scalars["String"]>;
  interface__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  interface__enabled__is_protected?: InputMaybe<Scalars["Boolean"]>;
  interface__enabled__is_visible?: InputMaybe<Scalars["Boolean"]>;
  interface__enabled__owner__id?: InputMaybe<Scalars["ID"]>;
  interface__enabled__source__id?: InputMaybe<Scalars["ID"]>;
  interface__enabled__value?: InputMaybe<Scalars["Boolean"]>;
  interface__enabled__values?: InputMaybe<Array<InputMaybe<Scalars["Boolean"]>>>;
  interface__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  interface__mtu__is_protected?: InputMaybe<Scalars["Boolean"]>;
  interface__mtu__is_visible?: InputMaybe<Scalars["Boolean"]>;
  interface__mtu__owner__id?: InputMaybe<Scalars["ID"]>;
  interface__mtu__source__id?: InputMaybe<Scalars["ID"]>;
  interface__mtu__value?: InputMaybe<Scalars["Int"]>;
  interface__mtu__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  interface__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  interface__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  interface__name__owner__id?: InputMaybe<Scalars["ID"]>;
  interface__name__source__id?: InputMaybe<Scalars["ID"]>;
  interface__name__value?: InputMaybe<Scalars["String"]>;
  interface__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  interface__role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  interface__role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  interface__role__owner__id?: InputMaybe<Scalars["ID"]>;
  interface__role__source__id?: InputMaybe<Scalars["ID"]>;
  interface__role__value?: InputMaybe<Scalars["String"]>;
  interface__role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  interface__speed__is_protected?: InputMaybe<Scalars["Boolean"]>;
  interface__speed__is_visible?: InputMaybe<Scalars["Boolean"]>;
  interface__speed__owner__id?: InputMaybe<Scalars["ID"]>;
  interface__speed__source__id?: InputMaybe<Scalars["ID"]>;
  interface__speed__value?: InputMaybe<Scalars["Int"]>;
  interface__speed__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  interface__status__is_protected?: InputMaybe<Scalars["Boolean"]>;
  interface__status__is_visible?: InputMaybe<Scalars["Boolean"]>;
  interface__status__owner__id?: InputMaybe<Scalars["ID"]>;
  interface__status__source__id?: InputMaybe<Scalars["ID"]>;
  interface__status__value?: InputMaybe<Scalars["String"]>;
  interface__status__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryInfraInterfaceArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  device__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  device__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  device__description__owner__id?: InputMaybe<Scalars["ID"]>;
  device__description__source__id?: InputMaybe<Scalars["ID"]>;
  device__description__value?: InputMaybe<Scalars["String"]>;
  device__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  device__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  device__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  device__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  device__name__owner__id?: InputMaybe<Scalars["ID"]>;
  device__name__source__id?: InputMaybe<Scalars["ID"]>;
  device__name__value?: InputMaybe<Scalars["String"]>;
  device__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  device__role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  device__role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  device__role__owner__id?: InputMaybe<Scalars["ID"]>;
  device__role__source__id?: InputMaybe<Scalars["ID"]>;
  device__role__value?: InputMaybe<Scalars["String"]>;
  device__role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  device__status__is_protected?: InputMaybe<Scalars["Boolean"]>;
  device__status__is_visible?: InputMaybe<Scalars["Boolean"]>;
  device__status__owner__id?: InputMaybe<Scalars["ID"]>;
  device__status__source__id?: InputMaybe<Scalars["ID"]>;
  device__status__value?: InputMaybe<Scalars["String"]>;
  device__status__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  device__type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  device__type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  device__type__owner__id?: InputMaybe<Scalars["ID"]>;
  device__type__source__id?: InputMaybe<Scalars["ID"]>;
  device__type__value?: InputMaybe<Scalars["String"]>;
  device__type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  enabled__is_protected?: InputMaybe<Scalars["Boolean"]>;
  enabled__is_visible?: InputMaybe<Scalars["Boolean"]>;
  enabled__owner__id?: InputMaybe<Scalars["ID"]>;
  enabled__source__id?: InputMaybe<Scalars["ID"]>;
  enabled__value?: InputMaybe<Scalars["Boolean"]>;
  enabled__values?: InputMaybe<Array<InputMaybe<Scalars["Boolean"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  mtu__is_protected?: InputMaybe<Scalars["Boolean"]>;
  mtu__is_visible?: InputMaybe<Scalars["Boolean"]>;
  mtu__owner__id?: InputMaybe<Scalars["ID"]>;
  mtu__source__id?: InputMaybe<Scalars["ID"]>;
  mtu__value?: InputMaybe<Scalars["Int"]>;
  mtu__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  role__owner__id?: InputMaybe<Scalars["ID"]>;
  role__source__id?: InputMaybe<Scalars["ID"]>;
  role__value?: InputMaybe<Scalars["String"]>;
  role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  speed__is_protected?: InputMaybe<Scalars["Boolean"]>;
  speed__is_visible?: InputMaybe<Scalars["Boolean"]>;
  speed__owner__id?: InputMaybe<Scalars["ID"]>;
  speed__source__id?: InputMaybe<Scalars["ID"]>;
  speed__value?: InputMaybe<Scalars["Int"]>;
  speed__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  status__is_protected?: InputMaybe<Scalars["Boolean"]>;
  status__is_visible?: InputMaybe<Scalars["Boolean"]>;
  status__owner__id?: InputMaybe<Scalars["ID"]>;
  status__source__id?: InputMaybe<Scalars["ID"]>;
  status__value?: InputMaybe<Scalars["String"]>;
  status__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  tags__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  tags__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  tags__description__owner__id?: InputMaybe<Scalars["ID"]>;
  tags__description__source__id?: InputMaybe<Scalars["ID"]>;
  tags__description__value?: InputMaybe<Scalars["String"]>;
  tags__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  tags__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  tags__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  tags__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  tags__name__owner__id?: InputMaybe<Scalars["ID"]>;
  tags__name__source__id?: InputMaybe<Scalars["ID"]>;
  tags__name__value?: InputMaybe<Scalars["String"]>;
  tags__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryInfraInterfaceL2Args = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  artifacts__checksum__is_protected?: InputMaybe<Scalars["Boolean"]>;
  artifacts__checksum__is_visible?: InputMaybe<Scalars["Boolean"]>;
  artifacts__checksum__owner__id?: InputMaybe<Scalars["ID"]>;
  artifacts__checksum__source__id?: InputMaybe<Scalars["ID"]>;
  artifacts__checksum__value?: InputMaybe<Scalars["String"]>;
  artifacts__checksum__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  artifacts__content_type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  artifacts__content_type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  artifacts__content_type__owner__id?: InputMaybe<Scalars["ID"]>;
  artifacts__content_type__source__id?: InputMaybe<Scalars["ID"]>;
  artifacts__content_type__value?: InputMaybe<Scalars["String"]>;
  artifacts__content_type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  artifacts__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  artifacts__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  artifacts__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  artifacts__name__owner__id?: InputMaybe<Scalars["ID"]>;
  artifacts__name__source__id?: InputMaybe<Scalars["ID"]>;
  artifacts__name__value?: InputMaybe<Scalars["String"]>;
  artifacts__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  artifacts__parameters__is_protected?: InputMaybe<Scalars["Boolean"]>;
  artifacts__parameters__is_visible?: InputMaybe<Scalars["Boolean"]>;
  artifacts__parameters__owner__id?: InputMaybe<Scalars["ID"]>;
  artifacts__parameters__source__id?: InputMaybe<Scalars["ID"]>;
  artifacts__parameters__value?: InputMaybe<Scalars["GenericScalar"]>;
  artifacts__parameters__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  artifacts__status__is_protected?: InputMaybe<Scalars["Boolean"]>;
  artifacts__status__is_visible?: InputMaybe<Scalars["Boolean"]>;
  artifacts__status__owner__id?: InputMaybe<Scalars["ID"]>;
  artifacts__status__source__id?: InputMaybe<Scalars["ID"]>;
  artifacts__status__value?: InputMaybe<Scalars["String"]>;
  artifacts__status__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  artifacts__storage_id__is_protected?: InputMaybe<Scalars["Boolean"]>;
  artifacts__storage_id__is_visible?: InputMaybe<Scalars["Boolean"]>;
  artifacts__storage_id__owner__id?: InputMaybe<Scalars["ID"]>;
  artifacts__storage_id__source__id?: InputMaybe<Scalars["ID"]>;
  artifacts__storage_id__value?: InputMaybe<Scalars["String"]>;
  artifacts__storage_id__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  connected_endpoint__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  device__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  device__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  device__description__owner__id?: InputMaybe<Scalars["ID"]>;
  device__description__source__id?: InputMaybe<Scalars["ID"]>;
  device__description__value?: InputMaybe<Scalars["String"]>;
  device__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  device__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  device__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  device__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  device__name__owner__id?: InputMaybe<Scalars["ID"]>;
  device__name__source__id?: InputMaybe<Scalars["ID"]>;
  device__name__value?: InputMaybe<Scalars["String"]>;
  device__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  device__role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  device__role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  device__role__owner__id?: InputMaybe<Scalars["ID"]>;
  device__role__source__id?: InputMaybe<Scalars["ID"]>;
  device__role__value?: InputMaybe<Scalars["String"]>;
  device__role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  device__status__is_protected?: InputMaybe<Scalars["Boolean"]>;
  device__status__is_visible?: InputMaybe<Scalars["Boolean"]>;
  device__status__owner__id?: InputMaybe<Scalars["ID"]>;
  device__status__source__id?: InputMaybe<Scalars["ID"]>;
  device__status__value?: InputMaybe<Scalars["String"]>;
  device__status__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  device__type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  device__type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  device__type__owner__id?: InputMaybe<Scalars["ID"]>;
  device__type__source__id?: InputMaybe<Scalars["ID"]>;
  device__type__value?: InputMaybe<Scalars["String"]>;
  device__type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  enabled__is_protected?: InputMaybe<Scalars["Boolean"]>;
  enabled__is_visible?: InputMaybe<Scalars["Boolean"]>;
  enabled__owner__id?: InputMaybe<Scalars["ID"]>;
  enabled__source__id?: InputMaybe<Scalars["ID"]>;
  enabled__value?: InputMaybe<Scalars["Boolean"]>;
  enabled__values?: InputMaybe<Array<InputMaybe<Scalars["Boolean"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  l2_mode__is_protected?: InputMaybe<Scalars["Boolean"]>;
  l2_mode__is_visible?: InputMaybe<Scalars["Boolean"]>;
  l2_mode__owner__id?: InputMaybe<Scalars["ID"]>;
  l2_mode__source__id?: InputMaybe<Scalars["ID"]>;
  l2_mode__value?: InputMaybe<Scalars["String"]>;
  l2_mode__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  mtu__is_protected?: InputMaybe<Scalars["Boolean"]>;
  mtu__is_visible?: InputMaybe<Scalars["Boolean"]>;
  mtu__owner__id?: InputMaybe<Scalars["ID"]>;
  mtu__source__id?: InputMaybe<Scalars["ID"]>;
  mtu__value?: InputMaybe<Scalars["Int"]>;
  mtu__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  role__owner__id?: InputMaybe<Scalars["ID"]>;
  role__source__id?: InputMaybe<Scalars["ID"]>;
  role__value?: InputMaybe<Scalars["String"]>;
  role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  speed__is_protected?: InputMaybe<Scalars["Boolean"]>;
  speed__is_visible?: InputMaybe<Scalars["Boolean"]>;
  speed__owner__id?: InputMaybe<Scalars["ID"]>;
  speed__source__id?: InputMaybe<Scalars["ID"]>;
  speed__value?: InputMaybe<Scalars["Int"]>;
  speed__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  status__is_protected?: InputMaybe<Scalars["Boolean"]>;
  status__is_visible?: InputMaybe<Scalars["Boolean"]>;
  status__owner__id?: InputMaybe<Scalars["ID"]>;
  status__source__id?: InputMaybe<Scalars["ID"]>;
  status__value?: InputMaybe<Scalars["String"]>;
  status__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  tagged_vlan__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  tagged_vlan__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  tagged_vlan__description__owner__id?: InputMaybe<Scalars["ID"]>;
  tagged_vlan__description__source__id?: InputMaybe<Scalars["ID"]>;
  tagged_vlan__description__value?: InputMaybe<Scalars["String"]>;
  tagged_vlan__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  tagged_vlan__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  tagged_vlan__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  tagged_vlan__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  tagged_vlan__name__owner__id?: InputMaybe<Scalars["ID"]>;
  tagged_vlan__name__source__id?: InputMaybe<Scalars["ID"]>;
  tagged_vlan__name__value?: InputMaybe<Scalars["String"]>;
  tagged_vlan__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  tagged_vlan__role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  tagged_vlan__role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  tagged_vlan__role__owner__id?: InputMaybe<Scalars["ID"]>;
  tagged_vlan__role__source__id?: InputMaybe<Scalars["ID"]>;
  tagged_vlan__role__value?: InputMaybe<Scalars["String"]>;
  tagged_vlan__role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  tagged_vlan__status__is_protected?: InputMaybe<Scalars["Boolean"]>;
  tagged_vlan__status__is_visible?: InputMaybe<Scalars["Boolean"]>;
  tagged_vlan__status__owner__id?: InputMaybe<Scalars["ID"]>;
  tagged_vlan__status__source__id?: InputMaybe<Scalars["ID"]>;
  tagged_vlan__status__value?: InputMaybe<Scalars["String"]>;
  tagged_vlan__status__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  tagged_vlan__vlan_id__is_protected?: InputMaybe<Scalars["Boolean"]>;
  tagged_vlan__vlan_id__is_visible?: InputMaybe<Scalars["Boolean"]>;
  tagged_vlan__vlan_id__owner__id?: InputMaybe<Scalars["ID"]>;
  tagged_vlan__vlan_id__source__id?: InputMaybe<Scalars["ID"]>;
  tagged_vlan__vlan_id__value?: InputMaybe<Scalars["Int"]>;
  tagged_vlan__vlan_id__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  tags__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  tags__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  tags__description__owner__id?: InputMaybe<Scalars["ID"]>;
  tags__description__source__id?: InputMaybe<Scalars["ID"]>;
  tags__description__value?: InputMaybe<Scalars["String"]>;
  tags__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  tags__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  tags__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  tags__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  tags__name__owner__id?: InputMaybe<Scalars["ID"]>;
  tags__name__source__id?: InputMaybe<Scalars["ID"]>;
  tags__name__value?: InputMaybe<Scalars["String"]>;
  tags__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  untagged_vlan__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  untagged_vlan__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  untagged_vlan__description__owner__id?: InputMaybe<Scalars["ID"]>;
  untagged_vlan__description__source__id?: InputMaybe<Scalars["ID"]>;
  untagged_vlan__description__value?: InputMaybe<Scalars["String"]>;
  untagged_vlan__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  untagged_vlan__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  untagged_vlan__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  untagged_vlan__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  untagged_vlan__name__owner__id?: InputMaybe<Scalars["ID"]>;
  untagged_vlan__name__source__id?: InputMaybe<Scalars["ID"]>;
  untagged_vlan__name__value?: InputMaybe<Scalars["String"]>;
  untagged_vlan__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  untagged_vlan__role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  untagged_vlan__role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  untagged_vlan__role__owner__id?: InputMaybe<Scalars["ID"]>;
  untagged_vlan__role__source__id?: InputMaybe<Scalars["ID"]>;
  untagged_vlan__role__value?: InputMaybe<Scalars["String"]>;
  untagged_vlan__role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  untagged_vlan__status__is_protected?: InputMaybe<Scalars["Boolean"]>;
  untagged_vlan__status__is_visible?: InputMaybe<Scalars["Boolean"]>;
  untagged_vlan__status__owner__id?: InputMaybe<Scalars["ID"]>;
  untagged_vlan__status__source__id?: InputMaybe<Scalars["ID"]>;
  untagged_vlan__status__value?: InputMaybe<Scalars["String"]>;
  untagged_vlan__status__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  untagged_vlan__vlan_id__is_protected?: InputMaybe<Scalars["Boolean"]>;
  untagged_vlan__vlan_id__is_visible?: InputMaybe<Scalars["Boolean"]>;
  untagged_vlan__vlan_id__owner__id?: InputMaybe<Scalars["ID"]>;
  untagged_vlan__vlan_id__source__id?: InputMaybe<Scalars["ID"]>;
  untagged_vlan__vlan_id__value?: InputMaybe<Scalars["Int"]>;
  untagged_vlan__vlan_id__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
};

export type QueryInfraInterfaceL3Args = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  artifacts__checksum__is_protected?: InputMaybe<Scalars["Boolean"]>;
  artifacts__checksum__is_visible?: InputMaybe<Scalars["Boolean"]>;
  artifacts__checksum__owner__id?: InputMaybe<Scalars["ID"]>;
  artifacts__checksum__source__id?: InputMaybe<Scalars["ID"]>;
  artifacts__checksum__value?: InputMaybe<Scalars["String"]>;
  artifacts__checksum__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  artifacts__content_type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  artifacts__content_type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  artifacts__content_type__owner__id?: InputMaybe<Scalars["ID"]>;
  artifacts__content_type__source__id?: InputMaybe<Scalars["ID"]>;
  artifacts__content_type__value?: InputMaybe<Scalars["String"]>;
  artifacts__content_type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  artifacts__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  artifacts__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  artifacts__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  artifacts__name__owner__id?: InputMaybe<Scalars["ID"]>;
  artifacts__name__source__id?: InputMaybe<Scalars["ID"]>;
  artifacts__name__value?: InputMaybe<Scalars["String"]>;
  artifacts__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  artifacts__parameters__is_protected?: InputMaybe<Scalars["Boolean"]>;
  artifacts__parameters__is_visible?: InputMaybe<Scalars["Boolean"]>;
  artifacts__parameters__owner__id?: InputMaybe<Scalars["ID"]>;
  artifacts__parameters__source__id?: InputMaybe<Scalars["ID"]>;
  artifacts__parameters__value?: InputMaybe<Scalars["GenericScalar"]>;
  artifacts__parameters__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  artifacts__status__is_protected?: InputMaybe<Scalars["Boolean"]>;
  artifacts__status__is_visible?: InputMaybe<Scalars["Boolean"]>;
  artifacts__status__owner__id?: InputMaybe<Scalars["ID"]>;
  artifacts__status__source__id?: InputMaybe<Scalars["ID"]>;
  artifacts__status__value?: InputMaybe<Scalars["String"]>;
  artifacts__status__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  artifacts__storage_id__is_protected?: InputMaybe<Scalars["Boolean"]>;
  artifacts__storage_id__is_visible?: InputMaybe<Scalars["Boolean"]>;
  artifacts__storage_id__owner__id?: InputMaybe<Scalars["ID"]>;
  artifacts__storage_id__source__id?: InputMaybe<Scalars["ID"]>;
  artifacts__storage_id__value?: InputMaybe<Scalars["String"]>;
  artifacts__storage_id__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  connected_endpoint__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  device__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  device__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  device__description__owner__id?: InputMaybe<Scalars["ID"]>;
  device__description__source__id?: InputMaybe<Scalars["ID"]>;
  device__description__value?: InputMaybe<Scalars["String"]>;
  device__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  device__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  device__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  device__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  device__name__owner__id?: InputMaybe<Scalars["ID"]>;
  device__name__source__id?: InputMaybe<Scalars["ID"]>;
  device__name__value?: InputMaybe<Scalars["String"]>;
  device__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  device__role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  device__role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  device__role__owner__id?: InputMaybe<Scalars["ID"]>;
  device__role__source__id?: InputMaybe<Scalars["ID"]>;
  device__role__value?: InputMaybe<Scalars["String"]>;
  device__role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  device__status__is_protected?: InputMaybe<Scalars["Boolean"]>;
  device__status__is_visible?: InputMaybe<Scalars["Boolean"]>;
  device__status__owner__id?: InputMaybe<Scalars["ID"]>;
  device__status__source__id?: InputMaybe<Scalars["ID"]>;
  device__status__value?: InputMaybe<Scalars["String"]>;
  device__status__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  device__type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  device__type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  device__type__owner__id?: InputMaybe<Scalars["ID"]>;
  device__type__source__id?: InputMaybe<Scalars["ID"]>;
  device__type__value?: InputMaybe<Scalars["String"]>;
  device__type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  enabled__is_protected?: InputMaybe<Scalars["Boolean"]>;
  enabled__is_visible?: InputMaybe<Scalars["Boolean"]>;
  enabled__owner__id?: InputMaybe<Scalars["ID"]>;
  enabled__source__id?: InputMaybe<Scalars["ID"]>;
  enabled__value?: InputMaybe<Scalars["Boolean"]>;
  enabled__values?: InputMaybe<Array<InputMaybe<Scalars["Boolean"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  ip_addresses__address__is_protected?: InputMaybe<Scalars["Boolean"]>;
  ip_addresses__address__is_visible?: InputMaybe<Scalars["Boolean"]>;
  ip_addresses__address__owner__id?: InputMaybe<Scalars["ID"]>;
  ip_addresses__address__source__id?: InputMaybe<Scalars["ID"]>;
  ip_addresses__address__value?: InputMaybe<Scalars["String"]>;
  ip_addresses__address__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ip_addresses__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  ip_addresses__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  ip_addresses__description__owner__id?: InputMaybe<Scalars["ID"]>;
  ip_addresses__description__source__id?: InputMaybe<Scalars["ID"]>;
  ip_addresses__description__value?: InputMaybe<Scalars["String"]>;
  ip_addresses__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ip_addresses__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  mtu__is_protected?: InputMaybe<Scalars["Boolean"]>;
  mtu__is_visible?: InputMaybe<Scalars["Boolean"]>;
  mtu__owner__id?: InputMaybe<Scalars["ID"]>;
  mtu__source__id?: InputMaybe<Scalars["ID"]>;
  mtu__value?: InputMaybe<Scalars["Int"]>;
  mtu__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  role__owner__id?: InputMaybe<Scalars["ID"]>;
  role__source__id?: InputMaybe<Scalars["ID"]>;
  role__value?: InputMaybe<Scalars["String"]>;
  role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  speed__is_protected?: InputMaybe<Scalars["Boolean"]>;
  speed__is_visible?: InputMaybe<Scalars["Boolean"]>;
  speed__owner__id?: InputMaybe<Scalars["ID"]>;
  speed__source__id?: InputMaybe<Scalars["ID"]>;
  speed__value?: InputMaybe<Scalars["Int"]>;
  speed__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  status__is_protected?: InputMaybe<Scalars["Boolean"]>;
  status__is_visible?: InputMaybe<Scalars["Boolean"]>;
  status__owner__id?: InputMaybe<Scalars["ID"]>;
  status__source__id?: InputMaybe<Scalars["ID"]>;
  status__value?: InputMaybe<Scalars["String"]>;
  status__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  tags__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  tags__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  tags__description__owner__id?: InputMaybe<Scalars["ID"]>;
  tags__description__source__id?: InputMaybe<Scalars["ID"]>;
  tags__description__value?: InputMaybe<Scalars["String"]>;
  tags__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  tags__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  tags__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  tags__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  tags__name__owner__id?: InputMaybe<Scalars["ID"]>;
  tags__name__source__id?: InputMaybe<Scalars["ID"]>;
  tags__name__value?: InputMaybe<Scalars["String"]>;
  tags__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryInfraLocationArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryInfraPlatformArgs = {
  ansible_network_os__is_protected?: InputMaybe<Scalars["Boolean"]>;
  ansible_network_os__is_visible?: InputMaybe<Scalars["Boolean"]>;
  ansible_network_os__owner__id?: InputMaybe<Scalars["ID"]>;
  ansible_network_os__source__id?: InputMaybe<Scalars["ID"]>;
  ansible_network_os__value?: InputMaybe<Scalars["String"]>;
  ansible_network_os__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  devices__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  devices__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  devices__description__owner__id?: InputMaybe<Scalars["ID"]>;
  devices__description__source__id?: InputMaybe<Scalars["ID"]>;
  devices__description__value?: InputMaybe<Scalars["String"]>;
  devices__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  devices__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  devices__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  devices__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  devices__name__owner__id?: InputMaybe<Scalars["ID"]>;
  devices__name__source__id?: InputMaybe<Scalars["ID"]>;
  devices__name__value?: InputMaybe<Scalars["String"]>;
  devices__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  devices__role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  devices__role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  devices__role__owner__id?: InputMaybe<Scalars["ID"]>;
  devices__role__source__id?: InputMaybe<Scalars["ID"]>;
  devices__role__value?: InputMaybe<Scalars["String"]>;
  devices__role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  devices__status__is_protected?: InputMaybe<Scalars["Boolean"]>;
  devices__status__is_visible?: InputMaybe<Scalars["Boolean"]>;
  devices__status__owner__id?: InputMaybe<Scalars["ID"]>;
  devices__status__source__id?: InputMaybe<Scalars["ID"]>;
  devices__status__value?: InputMaybe<Scalars["String"]>;
  devices__status__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  devices__type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  devices__type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  devices__type__owner__id?: InputMaybe<Scalars["ID"]>;
  devices__type__source__id?: InputMaybe<Scalars["ID"]>;
  devices__type__value?: InputMaybe<Scalars["String"]>;
  devices__type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  napalm_driver__is_protected?: InputMaybe<Scalars["Boolean"]>;
  napalm_driver__is_visible?: InputMaybe<Scalars["Boolean"]>;
  napalm_driver__owner__id?: InputMaybe<Scalars["ID"]>;
  napalm_driver__source__id?: InputMaybe<Scalars["ID"]>;
  napalm_driver__value?: InputMaybe<Scalars["String"]>;
  napalm_driver__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  netmiko_device_type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  netmiko_device_type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  netmiko_device_type__owner__id?: InputMaybe<Scalars["ID"]>;
  netmiko_device_type__source__id?: InputMaybe<Scalars["ID"]>;
  netmiko_device_type__value?: InputMaybe<Scalars["String"]>;
  netmiko_device_type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  nornir_platform__is_protected?: InputMaybe<Scalars["Boolean"]>;
  nornir_platform__is_visible?: InputMaybe<Scalars["Boolean"]>;
  nornir_platform__owner__id?: InputMaybe<Scalars["ID"]>;
  nornir_platform__source__id?: InputMaybe<Scalars["ID"]>;
  nornir_platform__value?: InputMaybe<Scalars["String"]>;
  nornir_platform__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryInfraSiteArgs = {
  address__is_protected?: InputMaybe<Scalars["Boolean"]>;
  address__is_visible?: InputMaybe<Scalars["Boolean"]>;
  address__owner__id?: InputMaybe<Scalars["ID"]>;
  address__source__id?: InputMaybe<Scalars["ID"]>;
  address__value?: InputMaybe<Scalars["String"]>;
  address__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  circuit_endpoints__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  circuit_endpoints__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  circuit_endpoints__description__owner__id?: InputMaybe<Scalars["ID"]>;
  circuit_endpoints__description__source__id?: InputMaybe<Scalars["ID"]>;
  circuit_endpoints__description__value?: InputMaybe<Scalars["String"]>;
  circuit_endpoints__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  circuit_endpoints__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  city__is_protected?: InputMaybe<Scalars["Boolean"]>;
  city__is_visible?: InputMaybe<Scalars["Boolean"]>;
  city__owner__id?: InputMaybe<Scalars["ID"]>;
  city__source__id?: InputMaybe<Scalars["ID"]>;
  city__value?: InputMaybe<Scalars["String"]>;
  city__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  contact__is_protected?: InputMaybe<Scalars["Boolean"]>;
  contact__is_visible?: InputMaybe<Scalars["Boolean"]>;
  contact__owner__id?: InputMaybe<Scalars["ID"]>;
  contact__source__id?: InputMaybe<Scalars["ID"]>;
  contact__value?: InputMaybe<Scalars["String"]>;
  contact__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  devices__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  devices__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  devices__description__owner__id?: InputMaybe<Scalars["ID"]>;
  devices__description__source__id?: InputMaybe<Scalars["ID"]>;
  devices__description__value?: InputMaybe<Scalars["String"]>;
  devices__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  devices__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  devices__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  devices__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  devices__name__owner__id?: InputMaybe<Scalars["ID"]>;
  devices__name__source__id?: InputMaybe<Scalars["ID"]>;
  devices__name__value?: InputMaybe<Scalars["String"]>;
  devices__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  devices__role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  devices__role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  devices__role__owner__id?: InputMaybe<Scalars["ID"]>;
  devices__role__source__id?: InputMaybe<Scalars["ID"]>;
  devices__role__value?: InputMaybe<Scalars["String"]>;
  devices__role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  devices__status__is_protected?: InputMaybe<Scalars["Boolean"]>;
  devices__status__is_visible?: InputMaybe<Scalars["Boolean"]>;
  devices__status__owner__id?: InputMaybe<Scalars["ID"]>;
  devices__status__source__id?: InputMaybe<Scalars["ID"]>;
  devices__status__value?: InputMaybe<Scalars["String"]>;
  devices__status__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  devices__type__is_protected?: InputMaybe<Scalars["Boolean"]>;
  devices__type__is_visible?: InputMaybe<Scalars["Boolean"]>;
  devices__type__owner__id?: InputMaybe<Scalars["ID"]>;
  devices__type__source__id?: InputMaybe<Scalars["ID"]>;
  devices__type__value?: InputMaybe<Scalars["String"]>;
  devices__type__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  parent__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  parent__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  parent__description__owner__id?: InputMaybe<Scalars["ID"]>;
  parent__description__source__id?: InputMaybe<Scalars["ID"]>;
  parent__description__value?: InputMaybe<Scalars["String"]>;
  parent__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  parent__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  parent__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  parent__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  parent__name__owner__id?: InputMaybe<Scalars["ID"]>;
  parent__name__source__id?: InputMaybe<Scalars["ID"]>;
  parent__name__value?: InputMaybe<Scalars["String"]>;
  parent__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  tags__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  tags__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  tags__description__owner__id?: InputMaybe<Scalars["ID"]>;
  tags__description__source__id?: InputMaybe<Scalars["ID"]>;
  tags__description__value?: InputMaybe<Scalars["String"]>;
  tags__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  tags__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  tags__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  tags__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  tags__name__owner__id?: InputMaybe<Scalars["ID"]>;
  tags__name__source__id?: InputMaybe<Scalars["ID"]>;
  tags__name__value?: InputMaybe<Scalars["String"]>;
  tags__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  vlans__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  vlans__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  vlans__description__owner__id?: InputMaybe<Scalars["ID"]>;
  vlans__description__source__id?: InputMaybe<Scalars["ID"]>;
  vlans__description__value?: InputMaybe<Scalars["String"]>;
  vlans__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  vlans__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  vlans__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  vlans__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  vlans__name__owner__id?: InputMaybe<Scalars["ID"]>;
  vlans__name__source__id?: InputMaybe<Scalars["ID"]>;
  vlans__name__value?: InputMaybe<Scalars["String"]>;
  vlans__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  vlans__role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  vlans__role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  vlans__role__owner__id?: InputMaybe<Scalars["ID"]>;
  vlans__role__source__id?: InputMaybe<Scalars["ID"]>;
  vlans__role__value?: InputMaybe<Scalars["String"]>;
  vlans__role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  vlans__status__is_protected?: InputMaybe<Scalars["Boolean"]>;
  vlans__status__is_visible?: InputMaybe<Scalars["Boolean"]>;
  vlans__status__owner__id?: InputMaybe<Scalars["ID"]>;
  vlans__status__source__id?: InputMaybe<Scalars["ID"]>;
  vlans__status__value?: InputMaybe<Scalars["String"]>;
  vlans__status__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  vlans__vlan_id__is_protected?: InputMaybe<Scalars["Boolean"]>;
  vlans__vlan_id__is_visible?: InputMaybe<Scalars["Boolean"]>;
  vlans__vlan_id__owner__id?: InputMaybe<Scalars["ID"]>;
  vlans__vlan_id__source__id?: InputMaybe<Scalars["ID"]>;
  vlans__vlan_id__value?: InputMaybe<Scalars["Int"]>;
  vlans__vlan_id__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
};

export type QueryInfraVlanArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  gateway__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  gateway__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  gateway__description__owner__id?: InputMaybe<Scalars["ID"]>;
  gateway__description__source__id?: InputMaybe<Scalars["ID"]>;
  gateway__description__value?: InputMaybe<Scalars["String"]>;
  gateway__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  gateway__enabled__is_protected?: InputMaybe<Scalars["Boolean"]>;
  gateway__enabled__is_visible?: InputMaybe<Scalars["Boolean"]>;
  gateway__enabled__owner__id?: InputMaybe<Scalars["ID"]>;
  gateway__enabled__source__id?: InputMaybe<Scalars["ID"]>;
  gateway__enabled__value?: InputMaybe<Scalars["Boolean"]>;
  gateway__enabled__values?: InputMaybe<Array<InputMaybe<Scalars["Boolean"]>>>;
  gateway__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  gateway__mtu__is_protected?: InputMaybe<Scalars["Boolean"]>;
  gateway__mtu__is_visible?: InputMaybe<Scalars["Boolean"]>;
  gateway__mtu__owner__id?: InputMaybe<Scalars["ID"]>;
  gateway__mtu__source__id?: InputMaybe<Scalars["ID"]>;
  gateway__mtu__value?: InputMaybe<Scalars["Int"]>;
  gateway__mtu__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  gateway__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  gateway__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  gateway__name__owner__id?: InputMaybe<Scalars["ID"]>;
  gateway__name__source__id?: InputMaybe<Scalars["ID"]>;
  gateway__name__value?: InputMaybe<Scalars["String"]>;
  gateway__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  gateway__role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  gateway__role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  gateway__role__owner__id?: InputMaybe<Scalars["ID"]>;
  gateway__role__source__id?: InputMaybe<Scalars["ID"]>;
  gateway__role__value?: InputMaybe<Scalars["String"]>;
  gateway__role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  gateway__speed__is_protected?: InputMaybe<Scalars["Boolean"]>;
  gateway__speed__is_visible?: InputMaybe<Scalars["Boolean"]>;
  gateway__speed__owner__id?: InputMaybe<Scalars["ID"]>;
  gateway__speed__source__id?: InputMaybe<Scalars["ID"]>;
  gateway__speed__value?: InputMaybe<Scalars["Int"]>;
  gateway__speed__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  gateway__status__is_protected?: InputMaybe<Scalars["Boolean"]>;
  gateway__status__is_visible?: InputMaybe<Scalars["Boolean"]>;
  gateway__status__owner__id?: InputMaybe<Scalars["ID"]>;
  gateway__status__source__id?: InputMaybe<Scalars["ID"]>;
  gateway__status__value?: InputMaybe<Scalars["String"]>;
  gateway__status__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  role__is_protected?: InputMaybe<Scalars["Boolean"]>;
  role__is_visible?: InputMaybe<Scalars["Boolean"]>;
  role__owner__id?: InputMaybe<Scalars["ID"]>;
  role__source__id?: InputMaybe<Scalars["ID"]>;
  role__value?: InputMaybe<Scalars["String"]>;
  role__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  site__address__is_protected?: InputMaybe<Scalars["Boolean"]>;
  site__address__is_visible?: InputMaybe<Scalars["Boolean"]>;
  site__address__owner__id?: InputMaybe<Scalars["ID"]>;
  site__address__source__id?: InputMaybe<Scalars["ID"]>;
  site__address__value?: InputMaybe<Scalars["String"]>;
  site__address__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  site__city__is_protected?: InputMaybe<Scalars["Boolean"]>;
  site__city__is_visible?: InputMaybe<Scalars["Boolean"]>;
  site__city__owner__id?: InputMaybe<Scalars["ID"]>;
  site__city__source__id?: InputMaybe<Scalars["ID"]>;
  site__city__value?: InputMaybe<Scalars["String"]>;
  site__city__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  site__contact__is_protected?: InputMaybe<Scalars["Boolean"]>;
  site__contact__is_visible?: InputMaybe<Scalars["Boolean"]>;
  site__contact__owner__id?: InputMaybe<Scalars["ID"]>;
  site__contact__source__id?: InputMaybe<Scalars["ID"]>;
  site__contact__value?: InputMaybe<Scalars["String"]>;
  site__contact__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  site__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  site__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  site__description__owner__id?: InputMaybe<Scalars["ID"]>;
  site__description__source__id?: InputMaybe<Scalars["ID"]>;
  site__description__value?: InputMaybe<Scalars["String"]>;
  site__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  site__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  site__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  site__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  site__name__owner__id?: InputMaybe<Scalars["ID"]>;
  site__name__source__id?: InputMaybe<Scalars["ID"]>;
  site__name__value?: InputMaybe<Scalars["String"]>;
  site__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  status__is_protected?: InputMaybe<Scalars["Boolean"]>;
  status__is_visible?: InputMaybe<Scalars["Boolean"]>;
  status__owner__id?: InputMaybe<Scalars["ID"]>;
  status__source__id?: InputMaybe<Scalars["ID"]>;
  status__value?: InputMaybe<Scalars["String"]>;
  status__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  vlan_id__is_protected?: InputMaybe<Scalars["Boolean"]>;
  vlan_id__is_visible?: InputMaybe<Scalars["Boolean"]>;
  vlan_id__owner__id?: InputMaybe<Scalars["ID"]>;
  vlan_id__source__id?: InputMaybe<Scalars["ID"]>;
  vlan_id__value?: InputMaybe<Scalars["Int"]>;
  vlan_id__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
};

export type QueryInfrahubTaskArgs = {
  ids?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  offset?: InputMaybe<Scalars["Int"]>;
  related_node__ids?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryLineageOwnerArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryLineageSourceArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type QueryRelationshipArgs = {
  excluded_namespaces?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids: Array<Scalars["String"]>;
  limit?: InputMaybe<Scalars["Int"]>;
  offset?: InputMaybe<Scalars["Int"]>;
};

export type QueryTestAllinoneArgs = {
  any__is_protected?: InputMaybe<Scalars["Boolean"]>;
  any__is_visible?: InputMaybe<Scalars["Boolean"]>;
  any__owner__id?: InputMaybe<Scalars["ID"]>;
  any__source__id?: InputMaybe<Scalars["ID"]>;
  any__value?: InputMaybe<Scalars["String"]>;
  any__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  anyy__is_protected?: InputMaybe<Scalars["Boolean"]>;
  anyy__is_visible?: InputMaybe<Scalars["Boolean"]>;
  anyy__owner__id?: InputMaybe<Scalars["ID"]>;
  anyy__source__id?: InputMaybe<Scalars["ID"]>;
  anyy__value?: InputMaybe<Scalars["GenericScalar"]>;
  anyy__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  bandwidth__is_protected?: InputMaybe<Scalars["Boolean"]>;
  bandwidth__is_visible?: InputMaybe<Scalars["Boolean"]>;
  bandwidth__owner__id?: InputMaybe<Scalars["ID"]>;
  bandwidth__source__id?: InputMaybe<Scalars["ID"]>;
  bandwidth__value?: InputMaybe<Scalars["Int"]>;
  bandwidth__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  boolean__is_protected?: InputMaybe<Scalars["Boolean"]>;
  boolean__is_visible?: InputMaybe<Scalars["Boolean"]>;
  boolean__owner__id?: InputMaybe<Scalars["ID"]>;
  boolean__source__id?: InputMaybe<Scalars["ID"]>;
  boolean__value?: InputMaybe<Scalars["Boolean"]>;
  boolean__values?: InputMaybe<Array<InputMaybe<Scalars["Boolean"]>>>;
  checkbox__is_protected?: InputMaybe<Scalars["Boolean"]>;
  checkbox__is_visible?: InputMaybe<Scalars["Boolean"]>;
  checkbox__owner__id?: InputMaybe<Scalars["ID"]>;
  checkbox__source__id?: InputMaybe<Scalars["ID"]>;
  checkbox__value?: InputMaybe<Scalars["Boolean"]>;
  checkbox__values?: InputMaybe<Array<InputMaybe<Scalars["Boolean"]>>>;
  color__is_protected?: InputMaybe<Scalars["Boolean"]>;
  color__is_visible?: InputMaybe<Scalars["Boolean"]>;
  color__owner__id?: InputMaybe<Scalars["ID"]>;
  color__source__id?: InputMaybe<Scalars["ID"]>;
  color__value?: InputMaybe<Scalars["String"]>;
  color__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  connected_endpoint__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  country__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  country__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  country__description__owner__id?: InputMaybe<Scalars["ID"]>;
  country__description__source__id?: InputMaybe<Scalars["ID"]>;
  country__description__value?: InputMaybe<Scalars["String"]>;
  country__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  country__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  country__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  country__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  country__name__owner__id?: InputMaybe<Scalars["ID"]>;
  country__name__source__id?: InputMaybe<Scalars["ID"]>;
  country__name__value?: InputMaybe<Scalars["String"]>;
  country__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  datetime__is_protected?: InputMaybe<Scalars["Boolean"]>;
  datetime__is_visible?: InputMaybe<Scalars["Boolean"]>;
  datetime__owner__id?: InputMaybe<Scalars["ID"]>;
  datetime__source__id?: InputMaybe<Scalars["ID"]>;
  datetime__value?: InputMaybe<Scalars["String"]>;
  datetime__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  dropdown__is_protected?: InputMaybe<Scalars["Boolean"]>;
  dropdown__is_visible?: InputMaybe<Scalars["Boolean"]>;
  dropdown__owner__id?: InputMaybe<Scalars["ID"]>;
  dropdown__source__id?: InputMaybe<Scalars["ID"]>;
  dropdown__value?: InputMaybe<Scalars["String"]>;
  dropdown__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  email__is_protected?: InputMaybe<Scalars["Boolean"]>;
  email__is_visible?: InputMaybe<Scalars["Boolean"]>;
  email__owner__id?: InputMaybe<Scalars["ID"]>;
  email__source__id?: InputMaybe<Scalars["ID"]>;
  email__value?: InputMaybe<Scalars["String"]>;
  email__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  file__is_protected?: InputMaybe<Scalars["Boolean"]>;
  file__is_visible?: InputMaybe<Scalars["Boolean"]>;
  file__owner__id?: InputMaybe<Scalars["ID"]>;
  file__source__id?: InputMaybe<Scalars["ID"]>;
  file__value?: InputMaybe<Scalars["String"]>;
  file__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  hashedpassword__is_protected?: InputMaybe<Scalars["Boolean"]>;
  hashedpassword__is_visible?: InputMaybe<Scalars["Boolean"]>;
  hashedpassword__owner__id?: InputMaybe<Scalars["ID"]>;
  hashedpassword__source__id?: InputMaybe<Scalars["ID"]>;
  hashedpassword__value?: InputMaybe<Scalars["String"]>;
  hashedpassword__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  idd__is_protected?: InputMaybe<Scalars["Boolean"]>;
  idd__is_visible?: InputMaybe<Scalars["Boolean"]>;
  idd__owner__id?: InputMaybe<Scalars["ID"]>;
  idd__source__id?: InputMaybe<Scalars["ID"]>;
  idd__value?: InputMaybe<Scalars["String"]>;
  idd__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  iphost__is_protected?: InputMaybe<Scalars["Boolean"]>;
  iphost__is_visible?: InputMaybe<Scalars["Boolean"]>;
  iphost__owner__id?: InputMaybe<Scalars["ID"]>;
  iphost__source__id?: InputMaybe<Scalars["ID"]>;
  iphost__value?: InputMaybe<Scalars["String"]>;
  iphost__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ipnetwork__is_protected?: InputMaybe<Scalars["Boolean"]>;
  ipnetwork__is_visible?: InputMaybe<Scalars["Boolean"]>;
  ipnetwork__owner__id?: InputMaybe<Scalars["ID"]>;
  ipnetwork__source__id?: InputMaybe<Scalars["ID"]>;
  ipnetwork__value?: InputMaybe<Scalars["String"]>;
  ipnetwork__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  json__is_protected?: InputMaybe<Scalars["Boolean"]>;
  json__is_visible?: InputMaybe<Scalars["Boolean"]>;
  json__owner__id?: InputMaybe<Scalars["ID"]>;
  json__source__id?: InputMaybe<Scalars["ID"]>;
  json__value?: InputMaybe<Scalars["GenericScalar"]>;
  json__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  list__is_protected?: InputMaybe<Scalars["Boolean"]>;
  list__is_visible?: InputMaybe<Scalars["Boolean"]>;
  list__owner__id?: InputMaybe<Scalars["ID"]>;
  list__source__id?: InputMaybe<Scalars["ID"]>;
  list__value?: InputMaybe<Scalars["GenericScalar"]>;
  list__values?: InputMaybe<Array<InputMaybe<Scalars["GenericScalar"]>>>;
  macaddress__is_protected?: InputMaybe<Scalars["Boolean"]>;
  macaddress__is_visible?: InputMaybe<Scalars["Boolean"]>;
  macaddress__owner__id?: InputMaybe<Scalars["ID"]>;
  macaddress__source__id?: InputMaybe<Scalars["ID"]>;
  macaddress__value?: InputMaybe<Scalars["String"]>;
  macaddress__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  member_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  member_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  member_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  number__is_protected?: InputMaybe<Scalars["Boolean"]>;
  number__is_visible?: InputMaybe<Scalars["Boolean"]>;
  number__owner__id?: InputMaybe<Scalars["ID"]>;
  number__source__id?: InputMaybe<Scalars["ID"]>;
  number__value?: InputMaybe<Scalars["Int"]>;
  number__values?: InputMaybe<Array<InputMaybe<Scalars["Int"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
  partial_match?: InputMaybe<Scalars["Boolean"]>;
  password__is_protected?: InputMaybe<Scalars["Boolean"]>;
  password__is_visible?: InputMaybe<Scalars["Boolean"]>;
  password__owner__id?: InputMaybe<Scalars["ID"]>;
  password__source__id?: InputMaybe<Scalars["ID"]>;
  password__value?: InputMaybe<Scalars["String"]>;
  password__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__description__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  subscriber_of_groups__label__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  subscriber_of_groups__name__value?: InputMaybe<Scalars["String"]>;
  subscriber_of_groups__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  tagone__description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  tagone__description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  tagone__description__owner__id?: InputMaybe<Scalars["ID"]>;
  tagone__description__source__id?: InputMaybe<Scalars["ID"]>;
  tagone__description__value?: InputMaybe<Scalars["String"]>;
  tagone__description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  tagone__ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  tagone__name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  tagone__name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  tagone__name__owner__id?: InputMaybe<Scalars["ID"]>;
  tagone__name__source__id?: InputMaybe<Scalars["ID"]>;
  tagone__name__value?: InputMaybe<Scalars["String"]>;
  tagone__name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  text__is_protected?: InputMaybe<Scalars["Boolean"]>;
  text__is_visible?: InputMaybe<Scalars["Boolean"]>;
  text__owner__id?: InputMaybe<Scalars["ID"]>;
  text__source__id?: InputMaybe<Scalars["ID"]>;
  text__value?: InputMaybe<Scalars["String"]>;
  text__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  textarea__is_protected?: InputMaybe<Scalars["Boolean"]>;
  textarea__is_visible?: InputMaybe<Scalars["Boolean"]>;
  textarea__owner__id?: InputMaybe<Scalars["ID"]>;
  textarea__source__id?: InputMaybe<Scalars["ID"]>;
  textarea__value?: InputMaybe<Scalars["String"]>;
  textarea__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  url__is_protected?: InputMaybe<Scalars["Boolean"]>;
  url__is_visible?: InputMaybe<Scalars["Boolean"]>;
  url__owner__id?: InputMaybe<Scalars["ID"]>;
  url__source__id?: InputMaybe<Scalars["ID"]>;
  url__value?: InputMaybe<Scalars["String"]>;
  url__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
};

export type RelatedNodeInput = {
  _relation__is_protected?: InputMaybe<Scalars["Boolean"]>;
  _relation__is_visible?: InputMaybe<Scalars["Boolean"]>;
  _relation__owner?: InputMaybe<Scalars["String"]>;
  _relation__source?: InputMaybe<Scalars["String"]>;
  id: Scalars["String"];
};

export type RelatedTaskLogCreateInput = {
  message: Scalars["String"];
  severity: Severity;
};

export type Relationship = {
  __typename?: "Relationship";
  id?: Maybe<Scalars["String"]>;
  identifier?: Maybe<Scalars["String"]>;
  peers?: Maybe<Array<Maybe<RelationshipPeer>>>;
};

export type RelationshipAdd = {
  __typename?: "RelationshipAdd";
  ok?: Maybe<Scalars["Boolean"]>;
};

export type RelationshipNode = {
  __typename?: "RelationshipNode";
  node?: Maybe<Relationship>;
};

export type RelationshipNodesInput = {
  /** ID of the node at the source of the relationship */
  id?: InputMaybe<Scalars["String"]>;
  /** Name of the relationship to add or remove nodes */
  name?: InputMaybe<Scalars["String"]>;
  /** List of nodes to add or remove to the relationships */
  nodes?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
};

export type RelationshipPeer = {
  __typename?: "RelationshipPeer";
  id?: Maybe<Scalars["String"]>;
  kind?: Maybe<Scalars["String"]>;
};

/** Defines properties for relationships */
export type RelationshipProperty = {
  __typename?: "RelationshipProperty";
  is_protected?: Maybe<Scalars["Boolean"]>;
  is_visible?: Maybe<Scalars["Boolean"]>;
  owner?: Maybe<LineageOwner>;
  source?: Maybe<LineageSource>;
  updated_at?: Maybe<Scalars["DateTime"]>;
};

export type RelationshipRemove = {
  __typename?: "RelationshipRemove";
  ok?: Maybe<Scalars["Boolean"]>;
};

export type Relationships = {
  __typename?: "Relationships";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<RelationshipNode>>>;
};

export type SchemaDropdownAdd = {
  __typename?: "SchemaDropdownAdd";
  object?: Maybe<DropdownFields>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type SchemaDropdownAddInput = {
  attribute: Scalars["String"];
  color?: InputMaybe<Scalars["String"]>;
  description?: InputMaybe<Scalars["String"]>;
  dropdown: Scalars["String"];
  kind: Scalars["String"];
  label?: InputMaybe<Scalars["String"]>;
};

export type SchemaDropdownRemove = {
  __typename?: "SchemaDropdownRemove";
  ok?: Maybe<Scalars["Boolean"]>;
};

export type SchemaDropdownRemoveInput = {
  attribute: Scalars["String"];
  dropdown: Scalars["String"];
  kind: Scalars["String"];
};

export type SchemaEnumAdd = {
  __typename?: "SchemaEnumAdd";
  ok?: Maybe<Scalars["Boolean"]>;
};

export type SchemaEnumInput = {
  attribute: Scalars["String"];
  enum: Scalars["String"];
  kind: Scalars["String"];
};

export type SchemaEnumRemove = {
  __typename?: "SchemaEnumRemove";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** An enumeration. */
export enum Severity {
  Critical = "CRITICAL",
  Error = "ERROR",
  Info = "INFO",
  Success = "SUCCESS",
  Warning = "WARNING",
}

export type Subscription = {
  __typename?: "Subscription";
  query?: Maybe<Scalars["GenericScalar"]>;
};

export type SubscriptionQueryArgs = {
  interval?: InputMaybe<Scalars["Int"]>;
  name?: InputMaybe<Scalars["String"]>;
  params?: InputMaybe<Scalars["GenericScalar"]>;
};

/** An enumeration. */
export enum TaskConclusion {
  Failure = "FAILURE",
  Success = "SUCCESS",
  Unknown = "UNKNOWN",
}

export type TaskCreate = {
  __typename?: "TaskCreate";
  object?: Maybe<TaskFields>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type TaskCreateInput = {
  conclusion: TaskConclusion;
  created_by?: InputMaybe<Scalars["String"]>;
  id?: InputMaybe<Scalars["UUID"]>;
  logs?: InputMaybe<Array<InputMaybe<RelatedTaskLogCreateInput>>>;
  related_node?: InputMaybe<Scalars["String"]>;
  title: Scalars["String"];
};

export type TaskFields = {
  __typename?: "TaskFields";
  conclusion?: Maybe<TaskConclusion>;
  id?: Maybe<Scalars["String"]>;
  title?: Maybe<Scalars["String"]>;
};

export type TaskLog = {
  __typename?: "TaskLog";
  id?: Maybe<Scalars["String"]>;
  message: Scalars["String"];
  severity: Scalars["String"];
  task_id: Scalars["String"];
  timestamp: Scalars["String"];
};

export type TaskLogEdge = {
  __typename?: "TaskLogEdge";
  edges?: Maybe<Array<Maybe<TaskLogNodes>>>;
};

export type TaskLogNodes = {
  __typename?: "TaskLogNodes";
  node?: Maybe<TaskLog>;
};

export type TaskNode = {
  __typename?: "TaskNode";
  conclusion: Scalars["String"];
  created_at: Scalars["String"];
  id: Scalars["String"];
  logs?: Maybe<TaskLogEdge>;
  related_node: Scalars["String"];
  related_node_kind: Scalars["String"];
  title: Scalars["String"];
  updated_at: Scalars["String"];
};

export type TaskNodes = {
  __typename?: "TaskNodes";
  node?: Maybe<TaskNode>;
};

export type TaskUpdate = {
  __typename?: "TaskUpdate";
  object?: Maybe<TaskFields>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type TaskUpdateInput = {
  conclusion?: InputMaybe<TaskConclusion>;
  id: Scalars["UUID"];
  logs?: InputMaybe<Array<InputMaybe<RelatedTaskLogCreateInput>>>;
  title?: InputMaybe<Scalars["String"]>;
};

export type Tasks = {
  __typename?: "Tasks";
  count?: Maybe<Scalars["Int"]>;
  edges?: Maybe<Array<Maybe<TaskNodes>>>;
};

/** object with all attributes */
export type TestAllinone = CoreNode &
  InfraEndpoint & {
    __typename?: "TestAllinone";
    _updated_at?: Maybe<Scalars["DateTime"]>;
    anyy?: Maybe<AnyAttribute>;
    bandwidth?: Maybe<NumberAttribute>;
    boolean?: Maybe<CheckboxAttribute>;
    checkbox?: Maybe<CheckboxAttribute>;
    color?: Maybe<TextAttribute>;
    connected_endpoint?: Maybe<NestedEdgedInfraEndpoint>;
    country?: Maybe<NestedEdgedInfraCountry>;
    datetime?: Maybe<TextAttribute>;
    display_label?: Maybe<Scalars["String"]>;
    dropdown?: Maybe<Dropdown>;
    email?: Maybe<TextAttribute>;
    file?: Maybe<TextAttribute>;
    hashedpassword?: Maybe<TextAttribute>;
    id: Scalars["String"];
    idd?: Maybe<TextAttribute>;
    iphost?: Maybe<IpHost>;
    ipnetwork?: Maybe<IpNetwork>;
    json?: Maybe<JsonAttribute>;
    list?: Maybe<ListAttribute>;
    macaddress?: Maybe<TextAttribute>;
    member_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    number?: Maybe<NumberAttribute>;
    password?: Maybe<TextAttribute>;
    subscriber_of_groups?: Maybe<NestedPaginatedCoreGroup>;
    tagone?: Maybe<NestedPaginatedBuiltinTag>;
    text?: Maybe<TextAttribute>;
    textarea?: Maybe<TextAttribute>;
    url?: Maybe<TextAttribute>;
  };

/** object with all attributes */
export type TestAllinoneMember_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** object with all attributes */
export type TestAllinoneSubscriber_Of_GroupsArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  label__is_protected?: InputMaybe<Scalars["Boolean"]>;
  label__is_visible?: InputMaybe<Scalars["Boolean"]>;
  label__owner__id?: InputMaybe<Scalars["ID"]>;
  label__source__id?: InputMaybe<Scalars["ID"]>;
  label__value?: InputMaybe<Scalars["String"]>;
  label__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** object with all attributes */
export type TestAllinoneTagoneArgs = {
  description__is_protected?: InputMaybe<Scalars["Boolean"]>;
  description__is_visible?: InputMaybe<Scalars["Boolean"]>;
  description__owner__id?: InputMaybe<Scalars["ID"]>;
  description__source__id?: InputMaybe<Scalars["ID"]>;
  description__value?: InputMaybe<Scalars["String"]>;
  description__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  ids?: InputMaybe<Array<InputMaybe<Scalars["ID"]>>>;
  limit?: InputMaybe<Scalars["Int"]>;
  name__is_protected?: InputMaybe<Scalars["Boolean"]>;
  name__is_visible?: InputMaybe<Scalars["Boolean"]>;
  name__owner__id?: InputMaybe<Scalars["ID"]>;
  name__source__id?: InputMaybe<Scalars["ID"]>;
  name__value?: InputMaybe<Scalars["String"]>;
  name__values?: InputMaybe<Array<InputMaybe<Scalars["String"]>>>;
  offset?: InputMaybe<Scalars["Int"]>;
};

/** object with all attributes */
export type TestAllinoneCreate = {
  __typename?: "TestAllinoneCreate";
  object?: Maybe<TestAllinone>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type TestAllinoneCreateInput = {
  anyy?: InputMaybe<AnyAttributeInput>;
  bandwidth?: InputMaybe<NumberAttributeInput>;
  boolean?: InputMaybe<CheckboxAttributeInput>;
  checkbox?: InputMaybe<CheckboxAttributeInput>;
  color?: InputMaybe<TextAttributeInput>;
  connected_endpoint?: InputMaybe<RelatedNodeInput>;
  country?: InputMaybe<RelatedNodeInput>;
  datetime?: InputMaybe<TextAttributeInput>;
  dropdown?: InputMaybe<TextAttributeInput>;
  email?: InputMaybe<TextAttributeInput>;
  file?: InputMaybe<TextAttributeInput>;
  hashedpassword?: InputMaybe<TextAttributeInput>;
  id?: InputMaybe<Scalars["String"]>;
  idd?: InputMaybe<TextAttributeInput>;
  iphost?: InputMaybe<TextAttributeInput>;
  ipnetwork?: InputMaybe<TextAttributeInput>;
  json?: InputMaybe<JsonAttributeInput>;
  list?: InputMaybe<ListAttributeInput>;
  macaddress?: InputMaybe<TextAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  number?: InputMaybe<NumberAttributeInput>;
  password?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  tagone?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  text?: InputMaybe<TextAttributeInput>;
  textarea?: InputMaybe<TextAttributeInput>;
  url?: InputMaybe<TextAttributeInput>;
};

/** object with all attributes */
export type TestAllinoneDelete = {
  __typename?: "TestAllinoneDelete";
  ok?: Maybe<Scalars["Boolean"]>;
};

/** object with all attributes */
export type TestAllinoneUpdate = {
  __typename?: "TestAllinoneUpdate";
  object?: Maybe<TestAllinone>;
  ok?: Maybe<Scalars["Boolean"]>;
};

export type TestAllinoneUpdateInput = {
  anyy?: InputMaybe<AnyAttributeInput>;
  bandwidth?: InputMaybe<NumberAttributeInput>;
  boolean?: InputMaybe<CheckboxAttributeInput>;
  checkbox?: InputMaybe<CheckboxAttributeInput>;
  color?: InputMaybe<TextAttributeInput>;
  connected_endpoint?: InputMaybe<RelatedNodeInput>;
  country?: InputMaybe<RelatedNodeInput>;
  datetime?: InputMaybe<TextAttributeInput>;
  dropdown?: InputMaybe<TextAttributeInput>;
  email?: InputMaybe<TextAttributeInput>;
  file?: InputMaybe<TextAttributeInput>;
  hashedpassword?: InputMaybe<TextAttributeInput>;
  id: Scalars["String"];
  idd?: InputMaybe<TextAttributeInput>;
  iphost?: InputMaybe<TextAttributeInput>;
  ipnetwork?: InputMaybe<TextAttributeInput>;
  json?: InputMaybe<JsonAttributeInput>;
  list?: InputMaybe<ListAttributeInput>;
  macaddress?: InputMaybe<TextAttributeInput>;
  member_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  number?: InputMaybe<NumberAttributeInput>;
  password?: InputMaybe<TextAttributeInput>;
  subscriber_of_groups?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  tagone?: InputMaybe<Array<InputMaybe<RelatedNodeInput>>>;
  text?: InputMaybe<TextAttributeInput>;
  textarea?: InputMaybe<TextAttributeInput>;
  url?: InputMaybe<TextAttributeInput>;
};

/** object with all attributes */
export type TestAllinoneUpsert = {
  __typename?: "TestAllinoneUpsert";
  object?: Maybe<TestAllinone>;
  ok?: Maybe<Scalars["Boolean"]>;
};

/** Attribute of type Text */
export type TextAttribute = AttributeInterface & {
  __typename?: "TextAttribute";
  id?: Maybe<Scalars["String"]>;
  is_inherited?: Maybe<Scalars["Boolean"]>;
  is_protected?: Maybe<Scalars["Boolean"]>;
  is_visible?: Maybe<Scalars["Boolean"]>;
  owner?: Maybe<LineageOwner>;
  source?: Maybe<LineageSource>;
  updated_at?: Maybe<Scalars["DateTime"]>;
  value?: Maybe<Scalars["String"]>;
};

export type TextAttributeInput = {
  is_protected?: InputMaybe<Scalars["Boolean"]>;
  is_visible?: InputMaybe<Scalars["Boolean"]>;
  owner?: InputMaybe<Scalars["String"]>;
  source?: InputMaybe<Scalars["String"]>;
  value?: InputMaybe<Scalars["String"]>;
};

export type ValueType = {
  __typename?: "ValueType";
  value: Scalars["String"];
};
