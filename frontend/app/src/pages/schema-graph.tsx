import { Icon } from "@iconify-icon/react";
import {
  SchemaVisualizer,
  type SchemaVisualizerData,
} from "@infrahub/schema-visualizer";
import { useAtomValue } from "jotai";
import { useMemo } from "react";
import {
  genericSchemasAtom,
  nodeSchemasAtom,
  profileSchemasAtom,
  templateSchemasAtom,
} from "@/entities/schema/stores/schema.atom";
import Content from "@/shared/components/layout/content";
import { LinkButton } from "@/shared/components/ui/button";
import { useTitle } from "@/shared/hooks/useTitle";

function SchemaGraphPage() {
	useTitle("Schema Graph");

	const nodes = useAtomValue(nodeSchemasAtom);
	const generics = useAtomValue(genericSchemasAtom);
	const profiles = useAtomValue(profileSchemasAtom);
	const templates = useAtomValue(templateSchemasAtom);

	// Prepare data for the visualizer
	const schemaData: SchemaVisualizerData = useMemo(
		() => ({
			nodes,
			generics,
			profiles,
			templates,
		}),
		[nodes, generics, profiles, templates],
	);

	// Calculate total schema count
	const totalCount = nodes.length + profiles.length + templates.length;

	return (
		<Content.Card className="flex h-[calc(100%-1rem)] flex-col">
			<Content.CardTitle
				title="Schema Graph"
				badgeContent={`${totalCount} schemas`}
				className="w-full"
				end={
					<LinkButton
						to="/schema"
						variant="outline"
						size="sm"
						className="ml-auto"
					>
						<Icon icon="mdi:format-list-bulleted" className="mr-2" />
						List View
					</LinkButton>
				}
			/>

			<div className="flex min-h-[500px] flex-1">
				<SchemaVisualizer data={schemaData} className="flex-1" />
			</div>
		</Content.Card>
	);
}

export function Component() {
	return <SchemaGraphPage />;
}
