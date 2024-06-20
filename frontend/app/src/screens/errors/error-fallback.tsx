import { Button } from "@/components/buttons/button-primitive";
import Accordion from "@/components/display/accordion";
import { Card } from "@/components/ui/card";
import Kbd from "@/components/ui/kbd";
import { Icon } from "@iconify-icon/react";
import { useEffect, useState } from "react";
import { useErrorBoundary } from "react-error-boundary";

type ErrorFallbackProps = {
  error: Error;
};
function ErrorFallback({ error }: ErrorFallbackProps) {
  const { resetBoundary } = useErrorBoundary();
  const [bugPosition, setBugPosition] = useState({ top: 0, left: 0 });

  useEffect(() => {
    const onKeydown = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() === "enter") {
        resetBoundary();
      }
      console.error(event.key);
      if (event.key.toLowerCase() === "backspace") {
        window.location.href = window.location.origin;
      }
    };

    document.addEventListener("keydown", onKeydown);
    return () => document.removeEventListener("keydown", onKeydown);
  }, []);

  const handleMoveOnBug = () => {
    const randomTop = bugPosition.top + Math.floor(Math.random() * 100) - 50;
    const randomLeft = bugPosition.left + Math.floor(Math.random() * 100) - 50;

    setBugPosition({
      top: randomTop,
      left: randomLeft,
    });
  };

  return (
    <div className="bg-gray-100 flex flex-col items-center justify-center h-screen">
      <Card className="flex flex-col items-center mb-4 p-4">
        <h1 className="font-semibold text-lg">Uh-oh, something went wrong :(</h1>

        <div>
          <p className="flex items-center gap-1">
            You might have encounter a{" "}
            <Icon
              icon="mdi:bug"
              className="relative text-custom-blue-600 transition-all text-xl cursor-pointer"
              style={bugPosition}
              onMouseEnter={handleMoveOnBug}
              onClick={handleMoveOnBug}
            />
            ...
          </p>

          <div>
            <Button className="mr-2" onClick={resetBoundary}>
              Refresh
            </Button>
            <a href={window.location.origin}>
              <Button variant="outline" className="my-4" onClick={resetBoundary}>
                Homepage
              </Button>
            </a>
          </div>

          <p className="font-medium text-xs mb-1">
            Press{" "}
            <Kbd keys={["enter"]} keyClassName="relative top-px mr-1">
              enter
            </Kbd>{" "}
            to try again
          </p>
          <p className="font-medium text-xs mb-4">
            Press{" "}
            <Kbd keys={["delete"]} keyClassName="mr-1">
              backspace
            </Kbd>{" "}
            to go back to Homepage
          </p>
        </div>
        <p className="text-xs text-gray-600">
          If this was unexpected, please reach out to us on{" "}
          <a
            className="underline"
            href="https://discord.com/channels/1212332642801025064/1212669187198025759"
            target="_blank"
            rel="noreferrer">
            Discord
          </a>
          {" or "}
          <a
            className="underline"
            href="https://github.com/opsmill/infrahub/issues/new/choose"
            target="_blank"
            rel="noreferrer">
            GitHub
          </a>
        </p>
      </Card>

      {error.stack && (
        <Accordion className="text-sm text-gray-600" title="View error stack">
          <pre className="p-2 rounded bg-red-50 text-red-800">{error.stack}</pre>
        </Accordion>
      )}
    </div>
  );
}

export default ErrorFallback;
