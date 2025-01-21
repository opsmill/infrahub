import { components } from "@/shared/api/rest/types.generated";
import { Button, LinkButton } from "@/shared/components/buttons/button-primitive";
import { CodeEditor } from "@/shared/components/editor/code-editor";
import Modal, { ModalTitle } from "@/shared/components/modals/modal";
import { Badge } from "@/shared/components/ui/badge";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { Icon } from "@iconify-icon/react";
import { useState } from "react";

export const ComputedAttributeDisplay = ({
  computedAttribute,
}: {
  computedAttribute?: components["schemas"]["ComputedAttribute-Output"] | null;
}) => {
  const [isOpen, setOpen] = useState(false);

  if (!computedAttribute) {
    return "-";
  }

  if (computedAttribute.kind === "Jinja2") {
    const fileData = JSON.stringify(computedAttribute.jinja2_template);
    const blob = new Blob([fileData], { type: "text/plain" });
    const url = URL.createObjectURL(blob);

    return (
      <div className="flex items-center gap-2">
        <Badge variant={"green-outline"}>Jinja2</Badge>

        <Button variant={"active-outline"} size={"icon"} onClick={() => setOpen(true)}>
          <Icon icon={"mdi:eye-outline"} />
        </Button>

        <Modal setOpen={setOpen} open={isOpen}>
          <div className="flex items-center gap-2 mb-2">
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
                <Icon icon={"mdi:download"} />
              </LinkButton>
            </Tooltip>
          </div>

          <CodeEditor value={computedAttribute.jinja2_template} disabled />
        </Modal>
      </div>
    );
  }

  return <div>OK</div>;
};
