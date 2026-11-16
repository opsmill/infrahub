import { useSetAtom } from "jotai";
import { useEffect, useId } from "react";

import { pageTitleRegistrationsAtom } from "@/shared/stores/page-title.atom";

export const useTitle = (title: string) => {
  const id = useId();
  const setRegistrations = useSetAtom(pageTitleRegistrationsAtom);

  // A title change keeps the registration's place, so a parent page that renames itself after loading
  // does not take the tab title back from a nested page.
  useEffect(() => {
    setRegistrations((registrations) =>
      registrations.some((registration) => registration.id === id)
        ? registrations.map((registration) =>
            registration.id === id ? { id, title } : registration
          )
        : [...registrations, { id, title }]
    );
  }, [id, title, setRegistrations]);

  useEffect(
    () => () => {
      setRegistrations((registrations) =>
        registrations.filter((registration) => registration.id !== id)
      );
    },
    [id, setRegistrations]
  );
};
