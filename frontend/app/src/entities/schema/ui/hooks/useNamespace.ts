import { useAtomValue } from "jotai";

import { namespacesAtom } from "@/entities/schema/stores/schema.atom";
import type { Namespace } from "@/entities/schema/types";

export const useNamespace = (namespace: string | null | undefined): Namespace | undefined => {
  const namespaces = useAtomValue(namespacesAtom);

  return namespaces.find((n) => {
    return n.name === namespace;
  });
};
