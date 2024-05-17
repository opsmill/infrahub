import { atom } from "jotai";
import * as R from "ramda";
import { TreeProps } from "../../../components/ui/tree";
import graphqlClient from "../../../graphql/graphqlClientApollo";
import {
  GET_PREFIX_ANCESTORS,
  GET_PREFIXES_ONLY,
  GET_TOP_LEVEL_PREFIXES,
} from "../../../graphql/queries/ipam/prefixes";
import { currentBranchAtom } from "../../../state/atoms/branches.atom";
import { datetimeAtom } from "../../../state/atoms/time.atom";
import { IP_PREFIX_GENERIC, IPAM_TREE_ROOT_ID } from "../constants";
import {
  AncestorsData,
  EMPTY_IPAM_TREE,
  formatIPPrefixResponseForTreeView,
  PrefixData,
  updateTreeData,
} from "./utils";

export const ipamTreeAtom = atom<TreeProps["data"]>(EMPTY_IPAM_TREE);

export const reloadIpamTreeAtom = atom(
  null,
  async (get, set, namespaceId: string, currentPrefixId?: string) => {
    const currentIpamTree = get(ipamTreeAtom);
    const currentBranch = get(currentBranchAtom);
    const timeMachineDate = get(datetimeAtom);

    const { data: getTopLevelPrefixData } = await graphqlClient.query<PrefixData>({
      query: GET_TOP_LEVEL_PREFIXES,
      variables: { namespaces: [namespaceId] },
      context: {
        branch: currentBranch?.name,
        date: timeMachineDate,
      },
    });

    if (!getTopLevelPrefixData) return currentIpamTree;

    const topLevelTreeItems = formatIPPrefixResponseForTreeView(getTopLevelPrefixData);
    const treeWithTopLevelPrefixesOnly = updateTreeData(
      EMPTY_IPAM_TREE,
      IPAM_TREE_ROOT_ID,
      topLevelTreeItems
    );

    if (!currentPrefixId) {
      set(ipamTreeAtom, treeWithTopLevelPrefixesOnly);
      return treeWithTopLevelPrefixesOnly;
    }

    const { data: getFetchPrefixAncestorsData } = await graphqlClient.query<AncestorsData>({
      query: GET_PREFIX_ANCESTORS,
      context: {
        branch: currentBranch?.name,
        date: timeMachineDate,
      },
      variables: {
        ids: [currentPrefixId],
        namespaces: [namespaceId],
      },
    });

    const prefixAncestorsData = getFetchPrefixAncestorsData[IP_PREFIX_GENERIC].edges[0];
    if (!prefixAncestorsData) {
      console.error(`Prefix ${currentPrefixId} not found.`);
      set(ipamTreeAtom, treeWithTopLevelPrefixesOnly);
      return treeWithTopLevelPrefixesOnly;
    }

    const ancestors = prefixAncestorsData.node.ancestors.edges.map(({ node }) => ({
      id: node.id,
      name: node.display_label,
      parentId: node.parent.node?.id ?? IPAM_TREE_ROOT_ID,
    }));

    const parentToChildMap: Record<string, string> = {};

    ancestors.forEach(({ id, parentId }) => {
      parentToChildMap[parentId] = id;
    });

    const orderedAncestorIds: string[] = [];

    const traverseHierarchy = (map: Record<string, string>, parentId: string) => {
      const childId = map[parentId];
      if (!childId) return;

      orderedAncestorIds.push(childId);
      traverseHierarchy(map, childId);
    };

    traverseHierarchy(parentToChildMap, IPAM_TREE_ROOT_ID);

    const { data: getFetchPrefixesData } = await graphqlClient.query<
      PrefixData,
      { parentIds: string[] }
    >({
      query: GET_PREFIXES_ONLY,
      context: {
        branch: currentBranch?.name,
        date: timeMachineDate,
      },
      variables: {
        parentIds: [...orderedAncestorIds, currentPrefixId],
      },
    });

    const newtreeItems = formatIPPrefixResponseForTreeView(getFetchPrefixesData);

    const groupedByParent = R.groupBy(
      (node) => node.parent?.toString() ?? IPAM_TREE_ROOT_ID,
      newtreeItems
    );

    const newTree = [...orderedAncestorIds, currentPrefixId].reduce((acc, currentAncestorId) => {
      const children = groupedByParent[currentAncestorId];
      if (!children) return acc;
      return updateTreeData(acc, currentAncestorId, children);
    }, treeWithTopLevelPrefixesOnly);

    set(ipamTreeAtom, newTree);
    return newTree;
  }
);
