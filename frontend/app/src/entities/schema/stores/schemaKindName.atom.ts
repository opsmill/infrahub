import { atom } from "jotai";

export interface iSchemaKindNameMap {
  [kind: string]: string;
}

export const schemaKindNameState = atom<iSchemaKindNameMap>({});
