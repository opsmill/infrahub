import { atom } from "jotai";
import { TreeProps } from "../../../components/ui/tree";
import { EMPTY_IPAM_TREE } from "./utils";

export const ipamTreeAtom = atom<TreeProps["data"]>(EMPTY_IPAM_TREE);
