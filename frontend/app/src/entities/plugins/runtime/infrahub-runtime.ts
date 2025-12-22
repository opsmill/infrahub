/**
 * InfrahubRuntime - Global runtime context for plugins
 *
 * This module exposes React and other shared dependencies as globals
 * so that runtime-loaded plugins can use them without bundling their own copies.
 *
 * Plugins built with the standard Vite config will reference these via:
 * - InfrahubRuntime.React
 * - InfrahubRuntime.ReactDOM
 * - InfrahubRuntime.jsxRuntime
 * - InfrahubRuntime.ReactRouter
 */

import * as React from "react";
import * as ReactDOM from "react-dom";
import * as jsxRuntime from "react/jsx-runtime";
import * as ReactRouter from "react-router";

export interface InfrahubRuntimeType {
  React: typeof React;
  ReactDOM: typeof ReactDOM;
  jsxRuntime: typeof jsxRuntime;
  ReactRouter: typeof ReactRouter;
  // Alias for compatibility - react-router v7 merged react-router-dom into react-router
  ReactRouterDOM: typeof ReactRouter;
}

// Create the runtime object
const runtime: InfrahubRuntimeType = {
  React,
  ReactDOM,
  jsxRuntime,
  ReactRouter,
  // react-router v7 includes everything from react-router-dom
  ReactRouterDOM: ReactRouter,
};

// Expose on window for plugins
declare global {
  interface Window {
    InfrahubRuntime: InfrahubRuntimeType;
    InfrahubPlugins: Record<string, { manifest: unknown; component: React.ComponentType<unknown> }>;
  }
}

// Extend window type for dev helper
declare global {
  interface Window {
    reloadPlugins?: () => Promise<void>;
  }
}

// Initialize globals
if (typeof window !== "undefined") {
  window.InfrahubRuntime = runtime;
  window.InfrahubPlugins = window.InfrahubPlugins || {};

  // Dev helper: call window.reloadPlugins() from browser console to reload plugins
  window.reloadPlugins = async () => {
    const { reloadRuntimePlugins } = await import("./plugin-loader");
    const plugins = await reloadRuntimePlugins();
    console.log("[Dev] Plugins reloaded:", plugins.map((p) => p.manifest.id));
    console.log("[Dev] Hard refresh (Ctrl+Shift+R) to see UI changes");
  };
}

export default runtime;
