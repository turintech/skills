import { H2, Link, Row, Stack, Stat, Text, useHostTheme } from "cursor/canvas";

/**
 * Answers: "Where did this metric start, and what is the best measured result?"
 * Snapshot inputs: baseline.metrics[metric], perMetricWinners[metric].raw,
 * metric metadata, run.baselineSha, and provenance.commands.
 * Customize labels and spacing; keep the raw winner primary and retain units,
 * counts, baseline SHA, and the mean-vs-baseline qualification.
 */
export type BaselineComparisonProps = {
  metric: string;
  unit: string;
  baseline: { mean: number; count: number };
  baselineSha: string;
  winner: {
    label: string;
    mean: number;
    count: number;
    pctBetter: number;
    webUrl?: string;
  };
  source: string;
};

function valueLabel(value: number, unit: string) {
  return `${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}${unit ? ` ${unit}` : ""}`;
}

export function BaselineComparison({
  metric,
  unit,
  baseline,
  baselineSha,
  winner,
  source,
}: BaselineComparisonProps) {
  const theme = useHostTheme();
  const signedPct = `${winner.pctBetter > 0 ? "+" : ""}${winner.pctBetter.toFixed(1)}%`;

  return (
    <Stack gap={8}>
      <H2>{metric}: baseline vs best measured version</H2>
      <Row gap={16} align="center">
        <Stat
          value={valueLabel(baseline.mean, unit)}
          label={`Baseline mean · n=${baseline.count}`}
        />
        <Stack gap={2} style={{ minWidth: 110, textAlign: "center" }}>
          <Text
            weight="semibold"
            style={{
              color:
                winner.pctBetter >= 0
                  ? theme.category.green
                  : theme.category.red,
            }}
          >
            {signedPct}
          </Text>
          <svg
            width="110"
            height="16"
            role="img"
            aria-label={`${metric} changed ${signedPct} from baseline to ${winner.label}`}
          >
            <line
              x1="4"
              y1="8"
              x2="102"
              y2="8"
              stroke={theme.accent.primary}
              strokeWidth="2"
            />
            <path
              d="M 96 3 L 104 8 L 96 13"
              fill="none"
              stroke={theme.accent.primary}
              strokeWidth="2"
            />
          </svg>
        </Stack>
        <Stat
          value={valueLabel(winner.mean, unit)}
          label={`${winner.label} mean · n=${winner.count}`}
          tone={winner.pctBetter >= 0 ? "success" : "danger"}
        />
      </Row>
      <Text size="small" tone="tertiary">
        Mean vs baseline {baselineSha}. Source: {source}.{" "}
        {winner.webUrl ? (
          <Link href={winner.webUrl}>Open {winner.label} in Artemis</Link>
        ) : null}
      </Text>
    </Stack>
  );
}
