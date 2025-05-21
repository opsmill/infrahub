import React from 'react';
import { translate } from '@docusaurus/Translate';

export default function EnterpriseBadge() {
  return (
    <span style={{
      backgroundColor: "#0a95ba",
      color: "white",
      padding: "4px 8px",
      borderRadius: "12px",
      fontSize: "1.2rem",
      fontWeight: "bold",
      marginLeft: "8px"
    }}>
      {translate({ message: 'Enterprise Edition' })}
    </span>
  );
}