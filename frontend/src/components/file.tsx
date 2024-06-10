import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import NoDataFound from "@/screens/errors/no-data-found";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { fetchStream } from "@/utils/fetch";
import { useCallback, useEffect, useState } from "react";
import { toast } from "react-toastify";
import { CodeEditor } from "./editor/code-editor";

type tFile = {
  url: string;
  enableCopy?: boolean;
};

export const File = (props: tFile) => {
  const { url, enableCopy } = props;

  const [isLoading, setIsLoading] = useState(false);
  const [fileContent, setFileContent] = useState("");

  const fetchFileDetails = useCallback(async () => {
    if (!url) return;

    setIsLoading(true);

    try {
      const fileResult = await fetchStream(url);

      setFileContent(fileResult);
    } catch (err) {
      console.error("err: ", err);
      toast(<Alert type={ALERT_TYPES.ERROR} message="Error while loading file content" />);
    }

    setIsLoading(false);
  }, []);

  useEffect(() => {
    fetchFileDetails();
  }, []);

  if (isLoading) {
    return <LoadingScreen />;
  }

  if (!fileContent) {
    return <NoDataFound message="No file found." />;
  }

  return (
    <div className="p-4">
      <CodeEditor value={fileContent} disabled enableCopy={enableCopy} />
    </div>
  );
};
