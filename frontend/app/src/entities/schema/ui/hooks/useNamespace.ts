import { namespacesAtom } from "@/entities/schema/stores/schema.atom";
import { Namespace } from "@/entities/schema/types";
import { useAtomValue } from "jotai";

export const useNamespace = (namespace: string | null | undefined): Namespace | undefined => {
  const namespaces = useAtomValue(namespacesAtom);

  return namespaces.find((n) => {
    return n.name === namespace;
  });
};
