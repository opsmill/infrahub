export const RESOURCE_GENERIC_KIND = "CoreResourcePool";
export const IP_ADDRESS_POOL = "CoreIPAddressPool";
export const IP_PREFIX_POOL = "CoreIPPrefixPool";
export const NUMBER_POOL_KIND = "CoreNumberPool";
export const NUMBER_POOL_NODE_FIELD = "node";
export const NUMBER_POOL_NODE_ATTRIBUTE_FIELD = "node_attribute";
export const MIN_PREFIX_LENGTH = 1;
export const MAX_PREFIX_LENGTH = 128;

/** Pool kinds, derived from the constants above so the literals stay single-sourced. */
export type IpPoolKind = typeof IP_ADDRESS_POOL | typeof IP_PREFIX_POOL;
export type NumberPoolKind = typeof NUMBER_POOL_KIND;
export type PoolKind = IpPoolKind | NumberPoolKind;
