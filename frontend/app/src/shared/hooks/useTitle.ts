import { useSetAtom } from "jotai";
import { useEffect, useId } from "react";

import { pageTitleRegistrationsAtom } from "@/shared/stores/page-title.atom";

export const useTitle = (title: string) => {
  const id = useId();
  const setRegistrations = useSetAtom(pageTitleRegistrationsAtom);

  useEffect(() => {
    setRegistrations((registrations) => [
      ...registrations.filter((registration) => registration.id !== id),
      { id, title },
    ]);

    return () => {
      setRegistrations((registrations) =>
        registrations.filter((registration) => registration.id !== id)
      );
    };
  }, [id, title, setRegistrations]);
};
