import { useAtomValue } from "jotai";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";

import { queryClient } from "@/shared/api/rest/client";
import { constructPath } from "@/shared/api/rest/fetch";
import { breadcrumbItemStyle } from "@/shared/components/layout/breadcrumb-navigation/style";
import {
  Combobox,
  ComboboxContent,
  ComboboxList,
  ComboboxTrigger,
} from "@/shared/components/ui/combobox";
import { CommandEmpty, CommandItem } from "@/shared/components/ui/command";
import { classNames } from "@/shared/utils/common";

import { getBranchesQueryOptions } from "@/entities/branches/domain/get-branches.query";
import { branchesState } from "@/entities/branches/stores";

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
    if (isOpen) queryClient.invalidateQueries(getBranchesQueryOptions());
  }, [isOpen]);

  return (
    <Combobox open={isOpen} onOpenChange={setIsOpen}>
      <ComboboxTrigger className={classNames(breadcrumbItemStyle, className)} {...props}>
        {value}
      </ComboboxTrigger>

      <ComboboxContent align="start" fitTriggerWidth={false}>
        <ComboboxList>
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
