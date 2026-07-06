import type { Filter } from "@/entities/nodes/filters/domain/model/filter";

export const AVAILABLE_IP_FILTER_NAME = "include_available" as const;
export const HIDE_AVAILABLE_IP_FILTER: Filter = { name: AVAILABLE_IP_FILTER_NAME, value: false };
export const HIDE_AVAILABLE_IP = "hide-available-ip";
export const SHOW_AVAILABLE_IP = "show-available-ip";
