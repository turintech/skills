import {
  H2,
  Link,
  Stack,
  Text,
  computeDAGLayout,
  useCanvasState,
  useHostTheme,
} from "cursor/canvas";

/**
 * Answers: "Which ideas or versions build on earlier work?"
 * Snapshot inputs: experiments, experiment parent IDs, and linked versions.
 * Build explicit nodes for the baseline, experiments, and versions. Edges mean
 * "was derived from"; do not infer lineage from generation order.
 */
export type LineageNode = {
  id: string;
  label: string;
  title: string;
  kind: "baseline" | "experiment" | "version";
  parentIds: string[];
  status?: string;
  summary?: string;
  webUrl?: string;
};

export type ExperimentLineageProps = {
  nodes: LineageNode[];
  stateKey?: string;
};

export function ExperimentLineage({
  nodes,
  stateKey = "experiment-lineage-focus",
}: ExperimentLineageProps) {
  const theme = useHostTheme();
  const [focusId, setFocusId] = useCanvasState(
    stateKey,
    nodes[0]?.id ?? "",
  );

  if (!nodes.length) return null;

  const nodeWidth = 180;
  const nodeHeight = 52;
  const layout = computeDAGLayout({
    nodes: nodes.map(({ id }) => ({ id })),
    edges: nodes.flatMap((node) =>
      node.parentIds.map((parentId) => ({ from: parentId, to: node.id })),
    ),
    direction: "horizontal",
    nodeWidth,
    nodeHeight,
    rankGap: 72,
    nodeGap: 28,
    padding: 20,
  });
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const focused = byId.get(focusId) ?? nodes[0];
  const nodeFill = (node: LineageNode) => {
    if (node.kind === "baseline") return theme.fill.tertiary;
    if (node.kind === "version") return theme.fill.secondary;
    return theme.bg.elevated;
  };

  return (
    <Stack gap={10}>
      <H2>Experiment and version lineage</H2>
      <div style={{ overflowX: "auto" }}>
        <svg
          width={layout.width}
          height={layout.height}
          role="img"
          aria-label="Directed lineage from baseline through experiments to generated versions"
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
                strokeDasharray={edge.isBackEdge ? "4 3" : undefined}
              />
            );
          })}
          {layout.nodes.map((position) => {
            const node = byId.get(position.id);
            if (!node) return null;
            const selected = node.id === focused.id;
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
                  fill={nodeFill(node)}
                  stroke={
                    selected ? theme.accent.primary : theme.stroke.secondary
                  }
                  strokeWidth={selected ? "2" : "1"}
                />
                <text
                  x={position.x + 10}
                  y={position.y + 20}
                  fill={theme.text.primary}
                  fontSize="12"
                  fontWeight="590"
                >
                  {node.label}
                </text>
                <text
                  x={position.x + 10}
                  y={position.y + 38}
                  fill={theme.text.secondary}
                  fontSize="10"
                >
                  {node.title.length > 27
                    ? `${node.title.slice(0, 26)}…`
                    : node.title}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
      <Stack gap={3}>
        <Text weight="semibold">
          {focused.label} · {focused.title}
        </Text>
        {focused.summary ? <Text>{focused.summary}</Text> : null}
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
