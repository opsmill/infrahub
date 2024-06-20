import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import { CONFIG } from "@/config/config";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { ApolloProvider } from "@apollo/client";
import { useSetAtom } from "jotai";
import { useEffect, useState } from "react";
import { RouterProvider } from "react-router-dom";
import { Slide, ToastContainer, toast } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import reportWebVitals from "./reportWebVitals";
import { Config, configState } from "./state/atoms/config.atom";

import LoadingScreen from "@/screens/loading-screen/loading-screen";

import { fetchUrl } from "@/utils/fetch";

import { router } from "@/router";
import { AuthProvider } from "@/hooks/useAuth";
import { addCollection } from "@iconify-icon/react";
import mdiIcons from "@iconify-json/mdi/icons.json";

import "./styles/index.css";
import "react-toastify/dist/ReactToastify.css";

addCollection(mdiIcons);

export const Infrahub = () => {
  const setConfig = useSetAtom(configState);
  const [isLoadingConfig, setIsLoadingConfig] = useState(true);

  const fetchConfig = async () => {
    try {
      return fetchUrl(CONFIG.CONFIG_URL);
    } catch (err) {
      toast(() => (
        <Alert type={ALERT_TYPES.ERROR} message="Something went wrong when fetching the config" />
      ));
      console.error("Error while fetching the config: ", err);
      return undefined;
    }
  };

  const setConfigInState = async () => {
    try {
      const config: Config = await fetchConfig();

      setConfig(config);
      setIsLoadingConfig(false);
    } catch (error: any) {
      setIsLoadingConfig(false);

      if (error?.message?.includes("Received status code 401")) {
        return;
      }

      toast(() => (
        <Alert type={ALERT_TYPES.ERROR} message="Something went wrong when fetching the config" />
      ));
      console.error("Error while fetching the config: ", error);
    }
  };

  useEffect(() => {
    setConfigInState();
  }, []);

  if (isLoadingConfig) {
    return (
      <div className="w-screen h-screen flex items-center justify-center">
        <LoadingScreen />
      </div>
    );
  }

  return (
    <AuthProvider>
      <ApolloProvider client={graphqlClient}>
        <ToastContainer
          hideProgressBar={true}
          transition={Slide}
          autoClose={5000}
          closeOnClick={false}
          newestOnTop
          position="bottom-right"
        />
        <RouterProvider router={router} />
      </ApolloProvider>
    </AuthProvider>
  );
};

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();
