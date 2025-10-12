import { useQueryState } from "nuqs";
import React from "react";

import { QSP } from "@/config/qsp";

import { getSchema } from "@/entities/schema/domain/get-schema";
import type { ModelSchema } from "@/entities/schema/types";
import { isGenericSchema } from "@/entities/schema/utils/is-generic-schema";

export const useSchemaSelectedInObjectTable = (schema: ModelSchema) => {
  const [kindInQsp, setKindInQsp] = useQueryState(QSP.KIND);

  React.useEffect(() => {
    if (!isGenericSchema(schema) || !schema.used_by?.find((kind) => kind === kindInQsp)) {
      setKindInQsp(null);
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
