import { atom } from "jotai";

export interface iSchemaKindLabelMap {
  [kind: string]: string;
}

export const schemaKindLabelState = atom<iSchemaKindLabelMap>({});
