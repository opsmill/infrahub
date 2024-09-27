import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import { CONFIG } from "@/config/config";
import { useSetAtom } from "jotai";
import { ReactNode, useEffect, useState } from "react";
import { toast } from "react-toastify";
import { Config, configState } from "./state/atoms/config.atom";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { fetchUrl } from "@/utils/fetch";

import { addCollection } from "@iconify-icon/react";
import mdiIcons from "@iconify-json/mdi/icons.json";

addCollection(mdiIcons);

export const Root = ({ children }: { children?: ReactNode }) => {
  const setConfig = useSetAtom(configState);
  const [isLoadingConfig, setIsLoadingConfig] = useState(true);

  const fetchConfig = async () => {
    try {
      return fetchUrl(CONFIG.CONFIG_URL);
    } catch (err) {
      toast(
        <Alert type={ALERT_TYPES.ERROR} message="Something went wrong when fetching the config" />
      );
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

      toast(
        <Alert type={ALERT_TYPES.ERROR} message="Something went wrong when fetching the config" />
      );
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

  return children;
};
