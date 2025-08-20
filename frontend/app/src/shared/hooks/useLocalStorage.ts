import { useState } from "react";

export function useLocalStorage(key: string): [string, (value: string) => void] {
  const [state, setState] = useState(localStorage.getItem(key) ?? "");

  const handleChange = (newValue: string) => {
    localStorage.setItem(key, newValue);
    setState(newValue);
  };

  return [state, handleChange];
}
