import { useAtomValue } from "jotai";

import type { Namespace } from "@/entities/schema/domain/model/types";
import { namespacesAtom } from "@/entities/schema/stores/schema.atom";

export const useNamespace = (namespace: string | null | undefined): Namespace | undefined => {
  const namespaces = useAtomValue(namespacesAtom);

  return namespaces.find((n) => {
    return n.name === namespace;
  });
};
