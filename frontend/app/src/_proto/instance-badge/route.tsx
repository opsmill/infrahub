// PROTOTYPE design-jam instance-badge
import { DesignHistory, type Knob, type Variant } from "./design-history-panel";
import { render as renderBannerStrip } from "./directions/banner-strip/rev-01";
import { render as renderHeaderLeft } from "./directions/header-left/rev-01";
import { render as renderHeaderRight } from "./directions/header-right/rev-01";
import { render as renderSidebarBrand } from "./directions/sidebar-brand/rev-01";
import {
  BAR_HEIGHT_DEFAULT,
  BAR_HEIGHT_MAX,
  BAR_HEIGHT_MIN,
  COLOR_OPTIONS,
  LABEL_OPTIONS,
  STRIP_HEIGHT_DEFAULT,
  STRIP_HEIGHT_MAX,
  STRIP_HEIGHT_MIN,
  STRIP_HEIGHT_STEP,
} from "./fixtures";

const REV_DATE = "2026-11-05";

const sharedKnobs: Knob[] = [
  {
    key: "label",
    label: "Label",
    type: "select",
    options: LABEL_OPTIONS,
    value: "zurich-west-2 PRODUCTION-MAIN",
  },
  { key: "color", label: "Color", type: "select", options: COLOR_OPTIONS, value: "red" },
  { key: "screen", label: "Screen", type: "select", options: ["app", "login"], value: "app" },
  {
    key: "sidebar",
    label: "Sidebar",
    type: "select",
    options: ["expanded", "collapsed"],
    value: "expanded",
  },
  { key: "theme", label: "Theme", type: "select", options: ["light", "dark"], value: "light" },
  {
    key: "barHeight",
    label: "Bar height (px)",
    type: "range",
    min: BAR_HEIGHT_MIN,
    max: BAR_HEIGHT_MAX,
    step: 1,
    value: BAR_HEIGHT_DEFAULT,
  },
];

const variants: Variant[] = [
  {
    id: "header-left",
    label: "Quiet pill, first in the header",
    bet: "The first thing the eye meets at the top-left of the content column is the instance, before the time selector and the branch; the tinted pill reads as a status, not a control.",
    revisions: [
      {
        rev: 1,
        note: "Tinted badge first in the header, thin bar above the whole layout",
        date: REV_DATE,
        render: renderHeaderLeft,
      },
    ],
  },
  {
    id: "header-right",
    label: "Status group, solid",
    bet: "The badge belongs with the other instance-level status indicators on the right, and a solid fill makes the color impossible to miss.",
    revisions: [
      {
        rev: 1,
        note: "Solid badge before the status icons, thin bar above the whole layout",
        date: REV_DATE,
        render: renderHeaderRight,
      },
    ],
  },
  {
    id: "banner-strip",
    label: "The bar carries the label",
    bet: "One element does both jobs: a strip across the top shows the label in the instance color, and the header stays exactly as it is today.",
    knobs: [
      {
        key: "stripHeight",
        label: "Strip height (px)",
        type: "range",
        min: STRIP_HEIGHT_MIN,
        max: STRIP_HEIGHT_MAX,
        step: STRIP_HEIGHT_STEP,
        value: STRIP_HEIGHT_DEFAULT,
      },
    ],
    revisions: [
      {
        rev: 1,
        note: "Labelled strip above the layout; thin bar when there is a color but no label",
        date: REV_DATE,
        render: renderBannerStrip,
      },
    ],
  },
  {
    id: "sidebar-brand",
    label: "Under the logo",
    bet: "The instance is part of the brand, so the label sits under the Infrahub logo where the eye lands when it looks for where am I; the header is untouched.",
    revisions: [
      {
        rev: 1,
        note: "Badge under the sidebar logo, colored dot when collapsed, thin bar above the layout",
        date: REV_DATE,
        render: renderSidebarBrand,
      },
    ],
  },
];

function InstanceBadgePrototype() {
  return <DesignHistory slug="instance-badge" variants={variants} knobs={sharedKnobs} />;
}

export const Component = InstanceBadgePrototype;
