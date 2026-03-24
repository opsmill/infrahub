import React, {useEffect} from 'react';
import Tabs from '@theme-original/Tabs';
import type TabsType from '@theme/Tabs';
import type {WrapperProps} from '@docusaurus/types';
import useIsBrowser from '@docusaurus/useIsBrowser';

type Props = WrapperProps<typeof TabsType>;

export default function TabsWrapper(props: Props): React.JSX.Element {
  const isBrowser = useIsBrowser();

  // On the client, read the query string BEFORE the first render
  // so that useState inside the original Tabs initializes with
  // the correct tab value instead of the default.
  let defaultValue = props.defaultValue;
  if (isBrowser && props.queryString && props.groupId) {
    const paramName =
      typeof props.queryString === 'string'
        ? props.queryString
        : props.groupId;
    const params = new URLSearchParams(window.location.search);
    const qsValue = params.get(paramName);
    if (qsValue) {
      defaultValue = qsValue;
    }
  }

  // After hydration, re-scroll to hash anchor since the correct
  // tab content is now visible.
  useEffect(() => {
    if (isBrowser && window.location.hash) {
      const id = decodeURIComponent(window.location.hash.slice(1));
      const el = document.getElementById(id);
      if (el) {
        requestAnimationFrame(() => {
          el.scrollIntoView();
        });
      }
    }
  }, [isBrowser]);

  return <Tabs key={String(isBrowser)} {...props} defaultValue={defaultValue} />;
}
