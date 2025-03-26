import React from "react";

export interface SearchAnywhereContextProps {
  isOpen: boolean;
  setIsOpen: (isOpen: boolean) => void;
  closeDialog: () => void;
  openDialog: () => void;
}

export const SearchAnywhereContext = React.createContext<SearchAnywhereContextProps>({
  isOpen: false,
  closeDialog: () => {},
  openDialog: () => {},
  setIsOpen: () => {},
});

export const useSearchAnywhereContext = () => {
  const context = React.use(SearchAnywhereContext);
  if (context === undefined) {
    throw new Error("useSearchAnywhereContext must be used within a SearchAnywhereContext");
  }
  return context;
};
