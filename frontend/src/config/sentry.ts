import * as Sentry from "@sentry/react";
import { BrowserTracing } from "@sentry/tracing";
import { Config } from "../state/atoms/config.atom";

const DEFAULT_DSN = "https://c271c704fe5a43b3b08c83919f0d8e01@o4504893920247808.ingest.sentry.io/4504893931520000";

const TRACING_INSTANCE = new BrowserTracing();

const REPLAY_INSTANCE = new Sentry.Replay();

// Flag to init or not Sentry
// TODO: find a better way to init the client from the config
let isInitialised = false;

const SentryClient = (config?: Config) => {
  if (!config?.logging?.remote?.enable) {
    return;
  }

  if (isInitialised) {
    return;
  }

  isInitialised = true;

  Sentry.init({
    dsn: config?.logging?.remote?.frontend_dsn ?? DEFAULT_DSN,
    integrations: [
      TRACING_INSTANCE,
      REPLAY_INSTANCE,
    ],
  });
};

export default SentryClient;
