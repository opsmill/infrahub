import { atom } from "jotai";

export type RemoteConfig = {
  api_server_dsn: string;
  enable: boolean;
  frontend_dsn: string;
  git_agent_dsn: string;
};

export type AnalyticsConfig = {
  address: string;
  api_key: string;
  enable: boolean;
};
export type LoggingConfig = {
  remote: RemoteConfig;
};
export type MainConfig = {
  default_branch: string;
  internal_address: string;
  allow_anonymous_access: boolean;
};

export type Config = {
  analytics: AnalyticsConfig;
  logging: LoggingConfig;
  main: MainConfig;
  experimental_features: { [key: string]: boolean };
};

export const configState = atom<Config | undefined>(undefined);
