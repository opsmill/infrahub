import { atom } from "jotai";
import { NodeSchema } from "../../generated/graphql";

export const schemaState = atom<NodeSchema[]>([]);
