import { useAtomValue } from "jotai";
import { useQueryState } from "nuqs";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { toast } from "react-toastify";

import { Col, Row } from "@/shared/components/container";
import { PanZoom } from "@/shared/components/display/pan-zoom";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { useFormatDate } from "@/shared/context/date-preferences-context";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import {
  RACK_COLOR_BY_QSP,
  RACK_LABEL_BY_QSP,
  type RackElevationItem,
  RackElevationRole,
  type RackFace,
  RackItemPlacement,
} from "@/entities/rack-elevation/domain/model/rack-elevation";
import { getMountableAttributeOptions } from "@/entities/rack-elevation/domain/rules/get-mountable-attribute-options";
import { toCsv } from "@/entities/rack-elevation/domain/rules/to-csv";
import {
  exportRackElevationCsv,
  exportRackElevationPng,
  exportRackElevationSvg,
} from "@/entities/rack-elevation/ui/export-rack-elevation";
import { useGetRackElevation } from "@/entities/rack-elevation/ui/queries/get-rack-elevation.query";
import { useGetRackElevationKinds } from "@/entities/rack-elevation/ui/queries/get-rack-elevation-kinds.query";
import { usePlaceRackItemMutation } from "@/entities/rack-elevation/ui/queries/place-rack-item.mutation";
import { RackElevationSvg, type UnitTarget } from "@/entities/rack-elevation/ui/rack-elevation-svg";
import {
  RackElevationToolbar,
  type RackExportFormat,
} from "@/entities/rack-elevation/ui/rack-elevation-toolbar";
import { RackItemSideList } from "@/entities/rack-elevation/ui/rack-item-side-list";
import { RackUnitActionSheet } from "@/entities/rack-elevation/ui/rack-unit-action-sheet";
import { genericSchemasAtom, nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

const toFileName = (rackName: string, extension: string) =>
  `${rackName.replaceAll(/[^\w-]+/g, "-")}-elevation.${extension}`;

export interface RackElevationViewProps {
  rackId: string;
}

export function RackElevationView({ rackId }: RackElevationViewProps) {
  const navigate = useNavigate();
  const { currentBranch } = useCurrentBranch();
  const { formatDate } = useFormatDate();
  const timeMachineDate = useAtomValue(datetimeAtom);
  const nodeSchemas = useAtomValue(nodeSchemasAtom);
  const genericSchemas = useAtomValue(genericSchemasAtom);
  const [labelBy, setLabelBy] = useQueryState(RACK_LABEL_BY_QSP);
  const [colorBy, setColorBy] = useQueryState(RACK_COLOR_BY_QSP);
  const [movingItemId, setMovingItemId] = useState<string | null>(null);
  const [actionTarget, setActionTarget] = useState<UnitTarget | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const {
    data: elevation,
    isPending,
    error,
    dataUpdatedAt,
  } = useGetRackElevation({
    rackId,
    labelBy,
    colorBy,
  });
  const { data: kinds = [] } = useGetRackElevationKinds();
  const placeItem = usePlaceRackItemMutation();

  const isMoveMode = movingItemId !== null;

  useEffect(() => {
    if (!isMoveMode) return;

    const exitOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMovingItemId(null);
    };
    window.addEventListener("keydown", exitOnEscape);
    return () => window.removeEventListener("keydown", exitOnEscape);
  }, [isMoveMode]);

  if (isPending) return <LoadingIndicator className="p-8" />;
  if (error) return <ErrorScreen message={error.message} />;

  const { rack, items } = elevation;
  const unpositionedItems = items.filter(
    ({ placement }) => placement === RackItemPlacement.UNPOSITIONED
  );
  const zeroUItems = items.filter(({ placement }) => placement === RackItemPlacement.ZERO_U);
  const attributeOptions = getMountableAttributeOptions({
    kinds,
    schemas: [...genericSchemas, ...nodeSchemas],
  });
  const mountableKinds = kinds
    .filter(({ role }) => role === RackElevationRole.MOUNTABLE)
    .map(({ kind }) => kind);
  const footerText = `${rack.display_label} · branch ${currentBranch.name} · data as of ${formatDate(
    timeMachineDate ?? new Date(dataUpdatedAt)
  )}`;

  const place = (itemId: string, position: number | null, face: RackFace | null) => {
    placeItem.mutate(
      { rackId, itemId, position, face },
      {
        onSuccess: () => {
          setMovingItemId(null);
          setActionTarget(null);
        },
        onError: (placementError) => {
          toast(<Alert type={ALERT_TYPES.ERROR} message={placementError.message} />);
        },
      }
    );
  };

  const openItem = (item: RackElevationItem) => navigate(getObjectDetailsUrl(item.kind, item.id));

  const selectUnit = ({ unit, face }: UnitTarget) => {
    if (movingItemId) {
      place(movingItemId, unit, face);
      return;
    }
    setActionTarget({ unit, face });
  };

  const exportElevation = async (format: RackExportFormat) => {
    const svg = svgRef.current;
    try {
      if (format === "csv") {
        exportRackElevationCsv(toCsv(rack, items), toFileName(rack.display_label, "csv"));
      } else if (svg && format === "svg") {
        exportRackElevationSvg(svg, toFileName(rack.display_label, "svg"));
      } else if (svg) {
        await exportRackElevationPng(svg, toFileName(rack.display_label, "png"));
      }
    } catch (exportError) {
      console.error("Error when exporting the rack elevation: ", exportError);
      toast(<Alert type={ALERT_TYPES.ERROR} message="The rack elevation could not be exported" />);
    }
  };

  return (
    <Col className="gap-4 p-4">
      <Row className="flex-wrap gap-6 text-sm" data-testid="rack-elevation-totals">
        <span>
          <strong>{rack.used_units}</strong> / {rack.u_height} U used
        </span>
        <span>
          <strong>{rack.utilization}%</strong> utilization
        </span>
        <span>
          Total weight:{" "}
          <strong>{rack.total_weight === null ? "not known" : `${rack.total_weight} kg`}</strong>
        </span>
        {isMoveMode && (
          <span className="text-blue-700">
            Click a unit to move the item there, or press Escape to cancel.
          </span>
        )}
      </Row>

      <RackElevationToolbar
        labelBy={labelBy}
        colorBy={colorBy}
        labelOptions={attributeOptions.labelBy}
        colorOptions={attributeOptions.colorBy}
        onLabelByChange={setLabelBy}
        onColorByChange={setColorBy}
        onExport={exportElevation}
      />

      <Row className="items-start gap-4">
        <PanZoom
          className="h-160 min-w-0 grow overflow-hidden rounded-lg border bg-content"
          isPanningDisabled={isMoveMode}
          panningExcludedClassNames={["rack-item"]}
        >
          <RackElevationSvg
            ref={svgRef}
            elevation={elevation}
            footerText={footerText}
            movingItemId={movingItemId}
            onOpenItem={openItem}
            onStartMove={(item) => setMovingItemId(item.id)}
            onSelectUnit={selectUnit}
          />
        </PanZoom>

        <Col className="w-72 shrink-0 gap-6">
          <RackItemSideList
            title="Not positioned"
            emptyMessage="Every item in this rack has a unit."
            items={unpositionedItems}
            selectedItemId={movingItemId}
            onItemPress={(item) => setMovingItemId(item.id)}
            data-testid="rack-list-unpositioned"
          />
          <RackItemSideList
            title="0U"
            emptyMessage="No 0U item in this rack."
            items={zeroUItems}
            selectedItemId={null}
            onItemPress={openItem}
            data-testid="rack-list-zero-u"
          />
        </Col>
      </Row>

      <RackUnitActionSheet
        target={actionTarget}
        rackName={rack.display_label}
        unpositionedItems={unpositionedItems}
        mountableKinds={mountableKinds}
        isPlacing={placeItem.isPending}
        onClose={() => setActionTarget(null)}
        onPlaceItem={(itemId) => {
          if (actionTarget) place(itemId, actionTarget.unit, actionTarget.face);
        }}
      />
    </Col>
  );
}
