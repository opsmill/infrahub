import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { NodeObject } from "@/entities/nodes/types";
import { ModelSchema } from "@/entities/schema/types";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { useAtomValue } from "jotai";
import { use } from "react";
import { FormContext, FormContextType } from "../../utils/form-context";
import { getDefaultParentFromApi } from "./get-default-parent-from-api";

type Node = {
  id: string;
  display_label: string;
  __typename: string;
};

interface DefaultValue {
  value?: {
    id?: string;
  } | null;
}

interface GetDefaultParentParams {
  defaultParent?: Node | null;
  currentParent?: Node | null;
  parentPeer?: string;
  formContext: FormContextType;
}

interface UseDefaultParentParams {
  defaultValue?: DefaultValue;
  parentRelationship?: {
    peer?: string;
    direction?: "bidirectional" | "inbound" | "outbound";
    identifier?: string;
  };
}

const convertNodeObjectToNode = (nodeObject: NodeObject | null): Node | null => {
  if (!nodeObject) return null;
  return {
    id: nodeObject.id,
    display_label: nodeObject.display_label || nodeObject.id,
    __typename: nodeObject.__typename,
  };
};

const getDefaultParent = ({
  currentParent,
  parentPeer,
  formContext,
}: GetDefaultParentParams): Node | null => {
  if (currentParent) {
    return currentParent;
  }

  if (
    parentPeer &&
    formContext.parentSchema &&
    isOfKind(parentPeer, formContext.parentSchema as ModelSchema)
  ) {
    return convertNodeObjectToNode(formContext.parentData);
  }

  return null;
};

export const useDefaultParent = ({ defaultValue, parentRelationship }: UseDefaultParentParams) => {
  const { currentBranch } = useCurrentBranch();

  const timeMachineDate = useAtomValue(datetimeAtom);

  const formContext = use(FormContext);

  const { data } = getDefaultParentFromApi({
    defaultValue,
    parentRelationship: parentRelationship || {},
    branchName: currentBranch.name,
    atDate: timeMachineDate,
  });

  const currentParent = data && data[parentRelationship?.peer]?.edges[0]?.node;

  return getDefaultParent({
    currentParent,
    parentPeer: parentRelationship?.peer,
    formContext,
  });
};
