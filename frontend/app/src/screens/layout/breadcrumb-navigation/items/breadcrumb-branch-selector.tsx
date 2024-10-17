import { Combobox, ComboboxContent, ComboboxList, ComboboxTrigger } from "@/components/ui/combobox";
import { CommandEmpty, CommandItem } from "@/components/ui/command";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { breadcrumbItemStyle } from "@/screens/layout/breadcrumb-navigation/style";
import { branchesState } from "@/state/atoms/branches.atom";
import { classNames } from "@/utils/common";
import { constructPath } from "@/utils/fetch";
import { useAtomValue } from "jotai";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

export default function BreadcrumbBranchSelector({
  value,
  className,
  ...props
}: {
  value: string;
  className?: string;
}) {
  const branches = useAtomValue(branchesState);
  const navigate = useNavigate();
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    if (isOpen) graphqlClient.refetchQueries({ include: ["GetBranches"] });
  }, [isOpen]);

  return (
    <Combobox open={isOpen} onOpenChange={setIsOpen}>
      <ComboboxTrigger className={classNames(breadcrumbItemStyle, className)} {...props}>
        {value}
      </ComboboxTrigger>

      <ComboboxContent align="start">
        <ComboboxList fitTriggerWidth={false}>
          <CommandEmpty>No branch found.</CommandEmpty>
          {branches.map((branch) => {
            const branchUrl = constructPath(`/branches/${branch.name}`);
            return (
              <CommandItem
                key={branch.name}
                value={branch.name}
                onSelect={() => {
                  setIsOpen(false);
                  navigate(branchUrl);
                }}
                asChild
              >
                <Link to={branchUrl}>{branch.name}</Link>
              </CommandItem>
            );
          })}
        </ComboboxList>
      </ComboboxContent>
    </Combobox>
  );
}
