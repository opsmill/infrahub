import { Transition as TransitionComponent } from "@headlessui/react";

export default function Transition(props: any) {
  return (
    <TransitionComponent
      enter="transition-opacity duration-200"
      enterFrom="opacity-0"
      enterTo="opacity-100"
      leave="transition-opacity duration-200"
      leaveFrom="opacity-100"
      leaveTo="opacity-0"
      {...props}>
      {props.children}
    </TransitionComponent>
  );
}
