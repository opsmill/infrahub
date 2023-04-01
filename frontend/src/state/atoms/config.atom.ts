import { atom } from "jotai";

export interface RemoteConfig {
  api_server_dsn: string,
  enable: boolean,
  frontend_dsn: string,
  git_agent_dsn: string,
}

export interface AnalyticsConfig {
  addres: string,
  api_key: string,
  enable: boolean,
}
export interface LoggingConfig {
  remote: RemoteConfig
}
export interface MainConfig {
  default_branch: string,
  internal_address: string,
}

export interface Config {
  analytics: AnalyticsConfig,
  logging: LoggingConfig,
  main: MainConfig,
}

export const configState = atom<Config | undefined>(undefined);
