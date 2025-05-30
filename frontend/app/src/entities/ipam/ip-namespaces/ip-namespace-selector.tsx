import { IpNamespace } from "@/entities/ipam/ip-namespaces/domain/get-ip-namespace-list";
import { useGetIpNamespaceList } from "@/entities/ipam/ip-namespaces/domain/get-ip-namespace-list.query";
import { useCurrentIpNamespace } from "@/entities/ipam/ip-namespaces/ui/ip-namespace-provider";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { constructPath } from "@/shared/api/rest/fetch";
import { Popover, PopoverTrigger } from "@/shared/components/aria/popover";
import { LinkButton } from "@/shared/components/buttons/button-primitive";
import { Col, Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import {
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
  ComboboxListProps,
} from "@/shared/components/ui/combobox";
import { Spinner } from "@/shared/components/ui/spinner";
import { focusVisibleStyle } from "@/shared/components/ui/style";
import { classNames, debounce } from "@/shared/utils/common";
import { ChevronsUpDownIcon } from "lucide-react";
import React from "react";
import { Button as AriaButton } from "react-aria-components";

interface IpNamespaceSelectorProps {
  className?: string;
}

export default function IpNamespaceSelector({ className }: IpNamespaceSelectorProps) {
  const { currentIpNamespace, setCurrentIpNamespace } = useCurrentIpNamespace();
  const [isOpen, setIsOpen] = React.useState(false);

  return (
    <div className={classNames("flex gap-2 items-center", className)}>
      <PopoverTrigger isOpen={isOpen} onOpenChange={setIsOpen}>
        <AriaButton
          data-testid="namespace-select"
          className={classNames(
            focusVisibleStyle,
            "flex flex-col w-full rounded-md p-1 m-1",
            "border border-transparent",
            "hover:bg-gray-100"
          )}
        >
          <Row className="text-xs text-gray-600">IP Namespace</Row>
          <Row className="text-sm">
            {getNodeLabel(currentIpNamespace)}
            <ChevronsUpDownIcon className="ml-auto text-gray-600 size-3.5" />
          </Row>
        </AriaButton>

        <Popover placement="bottom start" style={{ width: "var(--trigger-width)" }}>
          <IpNamespaceComboboxList
            onNamespaceSelection={(value) => {
              setCurrentIpNamespace(value);
              setIsOpen(false);
            }}
          />

          <Col className="border-t border-neutral-200">
            <LinkButton
              to={constructPath("/ipam/namespaces")}
              variant="ghost"
              size="sm"
              className="text-xs justify-start m-2"
            >
              View all IP namespaces
            </LinkButton>
          </Col>
        </Popover>
      </PopoverTrigger>
    </div>
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
        <Spinner className="flex justify-center m-2" />
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
                  <p className="text-xs truncate text-gray-500">{namespace.description?.value}</p>
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
