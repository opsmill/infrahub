import { keepPreviousData } from "@tanstack/react-query";
import { useSetAtom } from "jotai";
import type React from "react";
import { useEffect, useState } from "react";
import { toast } from "react-toastify";
import * as R from "remeda";

import ErrorScreen from "@/shared/components/errors/error-screen";
import { InfrahubLoading } from "@/shared/components/loading/infrahub-loading";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { sortByName, sortByOrderWeight } from "@/shared/utils/common";

import {
  genericSchemasAtom,
  namespacesAtom,
  nodeSchemasAtom,
  profileSchemasAtom,
  templateSchemasAtom,
} from "@/entities/schema/stores/schema.atom";
import { schemaKindLabelState } from "@/entities/schema/stores/schemaKindLabel.atom";
import { schemaKindNameState } from "@/entities/schema/stores/schemaKindName.atom";
import { useGetSchemaHash } from "@/entities/schema/ui/queries/get-schema-hash.query";
import { useLoadSchema } from "@/entities/schema/ui/queries/load-schema.query";

export const SchemaProvider = ({ children }: { children?: React.ReactNode }) => {
  const { data: schemaHash, error: errorHash } = useGetSchemaHash({
    placeholderData: keepPreviousData,
  });
  const { data: schemaData, error: errorSchema } = useLoadSchema(schemaHash, {
    enabled: !!schemaHash,
    staleTime: Infinity,
  });
  const [lastLoadedSchemaHash, setLastLoadedSchemaHash] = useState(""); // Current schema hash for tracking changes

  const setGenericSchemas = useSetAtom(genericSchemasAtom);
  const setNodeSchemas = useSetAtom(nodeSchemasAtom);
  const setProfileSchemas = useSetAtom(profileSchemasAtom);
  const setTemplateSchemas = useSetAtom(templateSchemasAtom);
  const setNamespaces = useSetAtom(namespacesAtom);
  const setSchemaKindNameState = useSetAtom(schemaKindNameState);
  const setSchemaKindLabelState = useSetAtom(schemaKindLabelState);

  useEffect(() => {
    if (!schemaData) return;
    try {
      const hash = schemaData.main;
      const nodeSchemas = sortByName(schemaData.nodes ?? []);
      const genericSchemas = sortByName(schemaData.generics || []);
      const profileSchemas = sortByName(schemaData.profiles || []);
      const templateSchemas = sortByName(schemaData.templates || []);
      const namespaces = sortByName(schemaData.namespaces || []);

      nodeSchemas.forEach((s) => {
        s.attributes = sortByOrderWeight(s.attributes || []);
        s.relationships = sortByOrderWeight(s.relationships || []);
      });

      const schemaKinds = [
        ...nodeSchemas.map((s) => s.kind),
        ...genericSchemas.map((s) => s.kind),
        ...profileSchemas.map((s) => s.kind),
        ...templateSchemas.map((s) => s.kind),
      ] as Array<string>;

      const schemaNames = [
        ...nodeSchemas.map((s) => s.name),
        ...genericSchemas.map((s) => s.name),
        ...profileSchemas.map((s) => s.name),
        ...templateSchemas.map((s) => s.name),
      ];
      const schemaKindNameMap = {
        ...R.fromEntries(R.zip(schemaKinds, schemaNames)),
        SchemaAttribute: "Attribute",
        SchemaRelationship: "Relationship",
        NodeKind: "Node",
      };

      const schemaLabels = [
        ...nodeSchemas.map((s) => s.label),
        ...genericSchemas.map((s) => s.label),
        ...profileSchemas.map((s) => s.label),
        ...templateSchemas.map((s) => s.label),
      ] as Array<string>;
      const schemaKindLabelMap = R.fromEntries(R.zip(schemaKinds, schemaLabels));

      setLastLoadedSchemaHash(hash);
      setGenericSchemas(genericSchemas);
      setNodeSchemas(nodeSchemas);
      setNamespaces(namespaces);
      setProfileSchemas(profileSchemas);
      setTemplateSchemas(templateSchemas);
      setSchemaKindNameState(schemaKindNameMap);
      setSchemaKindLabelState(schemaKindLabelMap);
    } catch (error) {
      toast(
        <Alert type={ALERT_TYPES.ERROR} message="Something went wrong when fetching the schema" />
      );

      console.error("Error while fetching the schema: ", error);
    }
  }, [schemaData]);

  const error = errorHash || errorSchema;
  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  if (lastLoadedSchemaHash !== schemaHash) {
    return <InfrahubLoading>Loading schemas...</InfrahubLoading>;
  }

  return children;
};
