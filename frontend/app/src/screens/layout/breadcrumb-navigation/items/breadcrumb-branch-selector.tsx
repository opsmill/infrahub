import { Combobox, ComboboxContent, ComboboxList, ComboboxTrigger } from "@/components/ui/combobox";
import { breadcrumbItemStyle } from "@/screens/layout/breadcrumb-navigation/style";
import React, { useEffect, useState } from "react";
import { useAtomValue } from "jotai";
import { branchesState } from "@/state/atoms/branches.atom";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { CommandEmpty, CommandItem } from "@/components/ui/command";
import { Link, useNavigate } from "react-router-dom";
import { constructPath } from "@/utils/fetch";
import { classNames } from "@/utils/common";

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
                asChild>
                <Link to={branchUrl}>{branch.name}</Link>
              </CommandItem>
            );
          })}
        </ComboboxList>
      </ComboboxContent>
    </Combobox>
  );
}
