import {
  H1,
  Link,
  Stack,
  Text,
  computeDAGLayout,
  useCanvasState,
  useHostTheme,
} from "cursor/canvas";

type StoryNode = {
  id: string;
  label: string;
  title: string;
  kind: "baseline" | "experiment" | "version";
  parentIds: string[];
  summary: string;
  status?: string;
  webUrl?: string;
};

// Complete composition example. Build these nodes from explicit experiment
// parent IDs and linked versions; generation order alone does not prove lineage.
const nodes: StoryNode[] = [
  {
    id: "baseline",
    label: "Baseline",
    title: "All-pairs traversal",
    kind: "baseline",
    parentIds: [],
    summary: "The original implementation measured before generated changes.",
  },
  {
    id: "experiment-grid",
    label: "Experiment A",
    title: "Reduce candidate pairs",
    kind: "experiment",
    parentIds: ["baseline"],
    status: "validated",
    summary: "Test whether a toroidal spatial grid reduces interaction work.",
  },
  {
    id: "v1",
    label: "v1",
    title: "Spatial grid",
    kind: "version",
    parentIds: ["experiment-grid"],
    summary: "Implements the first grid-based candidate search.",
    webUrl:
      "https://artemis.example/projects/project/discovery/run/versions/v1",
  },
  {
    id: "experiment-stream",
    label: "Experiment B",
    title: "Remove candidate buffer",
    kind: "experiment",
    parentIds: ["experiment-grid"],
    status: "validated",
    summary: "Build on the grid idea by streaming candidates into evaluation.",
  },
  {
    id: "v2",
    label: "v2",
    title: "Streaming grid",
    kind: "version",
    parentIds: ["experiment-stream"],
    summary: "Keeps the grid and removes candidate allocation and traversal.",
    webUrl:
      "https://artemis.example/projects/project/discovery/run/versions/v2",
  },
  {
    id: "experiment-cache",
    label: "Experiment C",
    title: "Cache coordinates",
    kind: "experiment",
    parentIds: ["baseline"],
    status: "refuted",
    summary: "Independently test coordinate caches on the all-pairs baseline.",
  },
  {
    id: "v3",
    label: "v3",
    title: "Coordinate cache",
    kind: "version",
    parentIds: ["experiment-cache"],
    summary: "Caches coordinates without adopting the spatial grid.",
    webUrl:
      "https://artemis.example/projects/project/discovery/run/versions/v3",
  },
];

export default function ExperimentStoryExample() {
  const theme = useHostTheme();
  const [focusId, setFocusId] = useCanvasState(
    "experiment-story-focus",
    "experiment-stream",
  );
  const nodeWidth = 170;
  const nodeHeight = 50;
  const layout = computeDAGLayout({
    nodes: nodes.map(({ id }) => ({ id })),
    edges: nodes.flatMap((node) =>
      node.parentIds.map((parentId) => ({ from: parentId, to: node.id })),
    ),
    direction: "horizontal",
    nodeWidth,
    nodeHeight,
    rankGap: 68,
    nodeGap: 24,
    padding: 20,
  });
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const focused = byId.get(focusId) ?? nodes[0];

  return (
    <Stack gap={16}>
      <Stack gap={5}>
        <H1>How experiments produced versions</H1>
        <Text tone="secondary">
          Select a node to inspect its intent, status, and platform link.
        </Text>
      </Stack>

      <div style={{ overflowX: "auto" }}>
        <svg
          width={layout.width}
          height={layout.height}
          role="img"
          aria-label="Experiment and version lineage from the baseline"
        >
          {layout.edges.map((edge, index) => {
            const midX = (edge.sourceX + edge.targetX) / 2;
            return (
              <path
                key={`${edge.from}-${edge.to}-${index}`}
                d={`M ${edge.sourceX} ${edge.sourceY} C ${midX} ${edge.sourceY}, ${midX} ${edge.targetY}, ${edge.targetX} ${edge.targetY}`}
                fill="none"
                stroke={theme.stroke.primary}
                strokeWidth="1.5"
              />
            );
          })}
          {layout.nodes.map((position) => {
            const node = byId.get(position.id);
            if (!node) return null;
            const selected = focused.id === node.id;
            return (
              <g
                key={node.id}
                role="button"
                tabIndex={0}
                aria-label={`Focus ${node.label}: ${node.title}`}
                onClick={() => setFocusId(node.id)}
                onKeyDown={(event: { key: string }) => {
                  if (event.key === "Enter" || event.key === " ") {
                    setFocusId(node.id);
                  }
                }}
                style={{ cursor: "pointer" }}
              >
                <rect
                  x={position.x}
                  y={position.y}
                  width={nodeWidth}
                  height={nodeHeight}
                  rx="6"
                  fill={
                    node.kind === "baseline"
                      ? theme.fill.tertiary
                      : node.kind === "version"
                        ? theme.fill.secondary
                        : theme.bg.elevated
                  }
                  stroke={
                    selected ? theme.accent.primary : theme.stroke.secondary
                  }
                  strokeWidth={selected ? "2" : "1"}
                />
                <text
                  x={position.x + 10}
                  y={position.y + 19}
                  fill={theme.text.primary}
                  fontSize="12"
                  fontWeight="590"
                >
                  {node.label}
                </text>
                <text
                  x={position.x + 10}
                  y={position.y + 36}
                  fill={theme.text.secondary}
                  fontSize="10"
                >
                  {node.title.length > 25
                    ? `${node.title.slice(0, 24)}…`
                    : node.title}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      <Stack gap={4}>
        <Text weight="semibold">
          {focused.label} · {focused.title}
        </Text>
        <Text>{focused.summary}</Text>
        <Text size="small" tone="tertiary">
          {focused.kind}
          {focused.status ? ` · ${focused.status}` : ""}
          {focused.webUrl ? (
            <>
              {" · "}
              <Link href={focused.webUrl}>Open in Artemis</Link>
            </>
          ) : null}
        </Text>
      </Stack>
    </Stack>
  );
}
