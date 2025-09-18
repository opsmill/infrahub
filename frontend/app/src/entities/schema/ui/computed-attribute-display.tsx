import { Icon } from "@iconify-icon/react";
import { useState } from "react";

import type { components } from "@/shared/api/rest/types.generated";
import { Button, LinkButton } from "@/shared/components/buttons/button-primitive";
import { CodeViewer } from "@/shared/components/editor/code/code-viewer";
import Modal, { ModalTitle } from "@/shared/components/modals/modal";
import { Badge } from "@/shared/components/ui/badge";
import { Tooltip } from "@/shared/components/ui/tooltip";

import { ModelDisplay } from "./styled";

export const ComputedAttributeDisplay = ({
  computedAttribute,
}: {
  computedAttribute?: components["schemas"]["ComputedAttribute-Output"] | null;
}) => {
  const [isOpen, setOpen] = useState(false);

  if (!computedAttribute) {
    return "-";
  }

  if (computedAttribute.kind === "Jinja2" && computedAttribute.jinja2_template) {
    const fileData = JSON.stringify(computedAttribute.jinja2_template);
    const blob = new Blob([fileData], { type: "text/plain" });
    const url = URL.createObjectURL(blob);

    return (
      <div className="flex items-center gap-2">
        <ModelDisplay kinds={["CoreTransformJinja2"]} />

        <Button
          variant={"active-outline"}
          size={"icon"}
          onClick={() => setOpen(true)}
          data-testid="jinja2-transform-button"
        >
          <Icon icon={"mdi:eye-outline"} />
        </Button>

        <Modal setOpen={setOpen} open={isOpen}>
          <div className="mb-2 flex items-center gap-2">
            <ModalTitle>Jinja2 Template</ModalTitle>

            <Tooltip enabled content="Download template">
              <LinkButton
                variant={"ghost"}
                size={"icon"}
                to={url}
                target="_blank"
                rel="noopener noreferrer"
                download={"jinja2-template.txt"}
              >
                <Icon icon={"mdi:download-outline"} />
              </LinkButton>
            </Tooltip>
          </div>

          <CodeViewer>{computedAttribute.jinja2_template}</CodeViewer>
        </Modal>
      </div>
    );
  }

  if (computedAttribute.kind === "TransformPython") {
    return (
      <div className="flex items-center gap-2">
        <ModelDisplay kinds={["CoreTransformPython"]} />

        <Badge variant={"gray-outline"}>{computedAttribute.transform}</Badge>
      </div>
    );
  }

  return null;
};
