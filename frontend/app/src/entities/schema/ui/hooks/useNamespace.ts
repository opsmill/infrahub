import { Namespace } from "@/entities/schema/types";
import { useAtomValue } from "jotai/index";
import { namespacesAtom } from "../../stores/schema.atom";

export const useNamespace = (namespace: string | null | undefined): Namespace | undefined => {
  const namespaces = useAtomValue(namespacesAtom);

  return namespaces.find((n) => {
    return n.name === namespace;
  });
};
