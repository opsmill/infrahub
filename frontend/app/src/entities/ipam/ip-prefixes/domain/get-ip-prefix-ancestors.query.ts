import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getIpPrefixAncestors } from "@/entities/ipam/ip-prefixes/domain/get-ip-prefix-ancestors";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai/index";

export function useGetIpPrefixAncestors(objectKind: string, objectId: string) {
  const { currentBranch } = useCurrentBranch();
  const atDate = useAtomValue(datetimeAtom);

  return useQuery({
    queryKey: ["objects", objectKind, objectId, "ancestors"],
    queryFn: () =>
      getIpPrefixAncestors({
        objectKind,
        objectId,
        branchName: currentBranch.name,
        atDate,
      }),
  });
}
