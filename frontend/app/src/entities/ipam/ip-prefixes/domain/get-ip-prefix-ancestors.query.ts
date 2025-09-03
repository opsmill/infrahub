import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getIpPrefixAncestors } from "@/entities/ipam/ip-prefixes/domain/get-ip-prefix-ancestors";
import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai/index";

export function useGetIpPrefixAncestors(objectKind: string, objectId: string) {
  const { currentBranch } = useCurrentBranch();
  const atDate = useAtomValue(datetimeAtom);

  const params = {
    branchName: currentBranch.name,
    atDate,
    objectKind,
    objectId,
  };

  return useQuery({
    queryKey: objectQueryKeys.ancestors(params),
    queryFn: () => getIpPrefixAncestors(params),
  });
}
