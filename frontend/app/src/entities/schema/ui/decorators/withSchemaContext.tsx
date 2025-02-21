import { CONFIG } from "@/config/config";
import { QSP } from "@/config/qsp";
import { branchesState, currentBranchAtom } from "@/entities/branches/stores";
import { findSelectedBranch } from "@/entities/branches/utils";
import {
  currentSchemaHashAtom,
  genericSchemasAtom,
  namespacesAtom,
  nodeSchemasAtom,
  profileSchemasAtom,
} from "@/entities/schema/stores/schema.atom";
import { schemaKindLabelState } from "@/entities/schema/stores/schemaKindLabel.atom";
import { schemaKindNameState } from "@/entities/schema/stores/schemaKindName.atom";
import { GenericSchema, Namespace, NodeSchema, ProfileSchema } from "@/entities/schema/types";
import { tokenSchema } from "@/entities/user-profile/ui/token-schema";
import { Branch } from "@/shared/api/graphql/generated/graphql";
import { fetchUrl } from "@/shared/api/rest/fetch";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { stateAtom } from "@/shared/stores/state.atom";
import { sortByName, sortByOrderWeight } from "@/shared/utils/common";
import { useAtom, useAtomValue, useSetAtom } from "jotai";
import * as R from "ramda";
import { createContext } from "react";
import { toast } from "react-toastify";
import { StringParam, useQueryParam } from "use-query-params";

type tSchemaContext = {
  checkSchemaUpdate: () => Promise<void>;
};

export const SchemaContext = createContext<tSchemaContext>({
  checkSchemaUpdate: async () => {},
});

export const withSchemaContext = (AppComponent: any) => (props: any) => {
  const [currentBranch, setCurrentBranch] = useAtom(currentBranchAtom);
  const [currentSchemaHash, setCurrentSchemaHash] = useAtom(currentSchemaHashAtom);
  const setSchema = useSetAtom(nodeSchemasAtom);
  const setSchemaKindNameState = useSetAtom(schemaKindNameState);
  const setSchemaKindLabelState = useSetAtom(schemaKindLabelState);
  const setGenerics = useSetAtom(genericSchemasAtom);
  const setNamespaces = useSetAtom(namespacesAtom);
  const setProfiles = useSetAtom(profileSchemasAtom);
  const setState = useSetAtom(stateAtom);
  const branches = useAtomValue(branchesState);
  const [branchInQueryString] = useQueryParam(QSP.BRANCH, StringParam);

  /**
   * Fetch schema from the backend, and store it
   */
  const fetchAndSetSchema = async (branch: Branch | null) => {
    try {
      const schemaData: {
        main: string;
        nodes: NodeSchema[];
        generics: GenericSchema[];
        namespaces: Namespace[];
        profiles: ProfileSchema[];
      } = await fetchUrl(CONFIG.SCHEMA_URL(branch?.name));

      const hash = schemaData.main;
      const schema = sortByName([...schemaData.nodes, tokenSchema]);
      const generics = sortByName(schemaData.generics || []);
      const namespaces = sortByName(schemaData.namespaces || []);
      const profiles = sortByName(schemaData.profiles || []);

      schema.forEach((s) => {
        s.attributes = sortByOrderWeight(s.attributes || []);
        s.relationships = sortByOrderWeight(s.relationships || []);
      });

      const schemaKinds = [
        ...schema.map((s) => s.kind),
        ...generics.map((s) => s.kind),
        ...profiles.map((s) => s.kind),
      ];

      const schemaNames = [
        ...schema.map((s) => s.label),
        ...generics.map((s) => s.label),
        ...profiles.map((s) => s.label),
      ];
      const schemaKindNameTuples = R.zip(schemaKinds, schemaNames);
      const schemaKindNameMap = {
        ...R.fromPairs(schemaKindNameTuples),
        SchemaAttribute: "Attribute",
        SchemaRelationship: "Relationship",
        SchemaNode: "Node",
      };

      const schemaLabels = [...schema.map((s) => s.label), ...generics.map((s) => s.label)];
      const schemaKindLabelTuples = R.zip(schemaKinds, schemaLabels);
      const schemaKindLabelMap = R.fromPairs(schemaKindLabelTuples);

      setGenerics(generics);
      setCurrentSchemaHash(hash);
      setSchema(schema);
      setSchemaKindNameState(schemaKindNameMap);
      setSchemaKindLabelState(schemaKindLabelMap);
      setNamespaces(namespaces);
      setProfiles(profiles);
      setState({ isReady: true });
    } catch (error) {
      toast(
        <Alert type={ALERT_TYPES.ERROR} message="Something went wrong when fetching the schema" />
      );

      console.error("Error while fetching the schema: ", error);
    }
  };

  const updateSchemaStateIfNeeded = async (branch: Branch | null) => {
    try {
      const schemaSummary = await fetchUrl(CONFIG.SCHEMA_SUMMARY_URL(branch?.name));
      const isSameSchema = currentSchemaHash === schemaSummary.main;

      // Updating schema only if it's different from the current one
      if (isSameSchema) return;
      await fetchAndSetSchema(branch);
    } catch (error) {
      console.error("Error while updating the schema state:", error);
    }
  };

  const checkSchemaUpdate = async () => {
    const selectedBranch = findSelectedBranch(branches, branchInQueryString);

    await updateSchemaStateIfNeeded(selectedBranch);

    if (selectedBranch?.name === currentBranch?.name) return;

    setCurrentBranch(selectedBranch);
  };

  const schemaContext = {
    checkSchemaUpdate,
  };

  return (
    <SchemaContext value={schemaContext}>
      <AppComponent {...props} />
    </SchemaContext>
  );
};
