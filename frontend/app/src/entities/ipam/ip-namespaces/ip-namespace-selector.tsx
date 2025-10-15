import { ChevronsUpDownIcon } from "lucide-react";
import React from "react";
import { Button as AriaButton } from "react-aria-components";

import { constructPath } from "@/shared/api/rest/fetch";
import { Popover, PopoverTrigger } from "@/shared/components/aria/popover";
import { LinkButton } from "@/shared/components/buttons/button-primitive";
import { Col, Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import {
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
  type ComboboxListProps,
} from "@/shared/components/ui/combobox";
import { Spinner } from "@/shared/components/ui/spinner";
import { focusVisibleStyle } from "@/shared/components/ui/style";
import { classNames, debounce } from "@/shared/utils/common";

import type { IpNamespace } from "@/entities/ipam/ip-namespaces/domain/get-ip-namespace-list";
import { useGetIpNamespaceList } from "@/entities/ipam/ip-namespaces/domain/get-ip-namespace-list.query";
import { useCurrentIpNamespace } from "@/entities/ipam/ip-namespaces/ui/ip-namespace-provider";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";

interface IpNamespaceSelectorProps {
  className?: string;
}

export default function IpNamespaceSelector({ className }: IpNamespaceSelectorProps) {
  const { currentIpNamespace, setCurrentIpNamespace } = useCurrentIpNamespace();
  const [isOpen, setIsOpen] = React.useState(false);

  return (
    <PopoverTrigger isOpen={isOpen} onOpenChange={setIsOpen}>
      <AriaButton
        data-testid="namespace-select"
        className={classNames(
          focusVisibleStyle,
          "flex h-10 w-full flex-col rounded px-1.5 py-0.5",
          "border border-transparent",
          "hover:bg-gray-100",
          className
        )}
      >
        <Row className="text-gray-600 text-xs">IP Namespace</Row>
        <Row className="gap-1.5 text-sm">
          <span className="truncate">{getNodeLabel(currentIpNamespace)}</span>
          <ChevronsUpDownIcon className="ml-auto size-3.5 shrink-0 text-gray-600" />
        </Row>
      </AriaButton>

      <Popover placement="bottom start" style={{ width: "var(--trigger-width)" }}>
        <IpNamespaceComboboxList
          onNamespaceSelection={(value) => {
            setCurrentIpNamespace(value);
            setIsOpen(false);
          }}
        />

        <Col className="border-neutral-200 border-t">
          <LinkButton
            to={constructPath("/ipam/namespaces")}
            variant="ghost"
            size="sm"
            className="m-2 justify-start text-xs"
          >
            View all IP namespaces
          </LinkButton>
        </Col>
      </Popover>
    </PopoverTrigger>
  );
}

interface IpNamespaceComboboxListProps extends ComboboxListProps {
  onNamespaceSelection: (value: IpNamespace) => void;
}

function IpNamespaceComboboxList({ onNamespaceSelection, ...props }: IpNamespaceComboboxListProps) {
  const [search, setSearch] = React.useState("");
  const { currentIpNamespace } = useCurrentIpNamespace();
  const { isPending, data, error, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useGetIpNamespaceList({
      filters: search ? [{ name: "any__value", value: search }] : undefined,
    });

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  const setSearchDebounced = debounce(setSearch, 300);

  return (
    <ComboboxList
      onValueChange={(newValue) => setSearchDebounced(newValue)}
      shouldFilter={false}
      {...props}
    >
      {isPending ? (
        <Spinner className="m-2 flex justify-center" />
      ) : (
        <>
          <ComboboxEmpty>No IP namespace found</ComboboxEmpty>

          {data.pages.map((page) => {
            return page.map((namespace) => (
              <ComboboxItem
                key={namespace.id}
                value={namespace.id}
                selectedValue={currentIpNamespace.id}
                onSelect={() => onNamespaceSelection(namespace)}
              >
                <div className="overflow-hidden">
                  <div className="truncate">{getNodeLabel(namespace)}</div>
                  <p className="truncate text-gray-500 text-xs">{namespace.description?.value}</p>
                </div>
              </ComboboxItem>
            ));
          })}
        </>
      )}

      {hasNextPage && (
        <ComboboxItem
          value="Load more"
          onSelect={() => fetchNextPage()}
          disabled={!hasNextPage || isFetchingNextPage}
          className="justify-center text-custom-blue-700"
        >
          {isFetchingNextPage ? "Loading more..." : "Load more"}
        </ComboboxItem>
      )}
    </ComboboxList>
  );
}
