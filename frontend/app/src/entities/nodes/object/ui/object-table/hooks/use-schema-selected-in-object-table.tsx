import React from "react";
import { StringParam, useQueryParam } from "use-query-params";

import { QSP } from "@/config/qsp";

import { getSchema } from "@/entities/schema/domain/get-schema";
import { ModelSchema } from "@/entities/schema/types";
import { isGenericSchema } from "@/entities/schema/utils/is-generic-schema";

export const useSchemaSelectedInObjectTable = (schema: ModelSchema) => {
  const [kindInQsp, setKindInQsp] = useQueryParam(QSP.KIND, StringParam);

  React.useEffect(() => {
    if (!isGenericSchema(schema) || !schema.used_by?.find((kind) => kind === kindInQsp)) {
      return setKindInQsp(undefined, "replaceIn");
    }
  }, [kindInQsp, schema.hash]);

  return React.useMemo<ModelSchema>(() => {
    if (!isGenericSchema(schema)) return schema;

    if (schema.used_by?.length === 1) {
      const singleInheritingKind = schema.used_by[0] as string;
      const { schema: schemaOfSingleInheritingKind } = getSchema(singleInheritingKind);
      if (schemaOfSingleInheritingKind) return schemaOfSingleInheritingKind;
    }

    if (!kindInQsp) return schema;

    const inheritingKindInQsp = schema.used_by?.find((kind) => kind === kindInQsp);
    if (!inheritingKindInQsp) return schema;

    const { schema: schemaOfInheritingKindInQsp } = getSchema(inheritingKindInQsp);
    if (!schemaOfInheritingKindInQsp) return schema;

    return schemaOfInheritingKindInQsp;
  }, [kindInQsp, schema.hash]);
};
