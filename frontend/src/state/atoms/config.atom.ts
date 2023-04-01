import { atom } from "jotai";

export interface Config {

}

export const configState = atom<Config | undefined>(undefined);
