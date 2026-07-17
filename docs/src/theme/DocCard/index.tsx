import React, { type ReactNode } from 'react';
import DocCard from '@theme-original/DocCard';
import type DocCardType from '@theme/DocCard';
import type { WrapperProps } from '@docusaurus/types';
import clsx from 'clsx';
import styles from './styles.module.css';

type Props = WrapperProps<typeof DocCardType>;

// Maps the `type` set via a doc's `sidebar_custom_props` (or a sidebar
// category's `customProps`) to a human-readable badge label.
const TYPE_LABELS: Record<string, string> = {
  release: 'Release',
  update: 'Update',
  security: 'Security',
};

export default function DocCardWrapper(props: Props): ReactNode {
  const type = (props.item as { customProps?: { type?: string } })?.customProps
    ?.type;
  const label = type ? TYPE_LABELS[type] : undefined;

  // No recognized type -> render the stock card untouched.
  if (!label) {
    return <DocCard {...props} />;
  }

  return (
    <div className={styles.cardWrapper}>
      <span className={clsx(styles.badge, styles[`badge_${type}`])}>{label}</span>
      <DocCard {...props} />
    </div>
  );
}
