import { H2, Link, Row, Stack, Text, useHostTheme } from "cursor/canvas";

/**
 * Answers: "Which versions improved or regressed most?"
 * Snapshot input: rankings[metric], enriched with each version's web URL.
 * Pass collector order unchanged. Color communicates pctBetter direction only;
 * it is not an experiment verdict or eligibility judgment.
 */
export type RankedVersion = {
  label: string;
  title: string;
  mean: number;
  pctBetter: number;
  webUrl?: string;
};

export type VersionRankingProps = {
  metric: string;
  unit: string;
  baselineSha: string;
  rows: RankedVersion[];
  source: string;
};

export function VersionRanking({
  metric,
  unit,
  baselineSha,
  rows,
  source,
}: VersionRankingProps) {
  const theme = useHostTheme();

  if (!rows.length) return null;

  return (
    <Stack gap={8}>
      <H2>{metric}: versions ranked by mean vs baseline</H2>
      <Stack gap={0}>
        {rows.map((row, index) => (
          <div key={row.label}>
            <Row
              gap={12}
              align="center"
              justify="space-between"
              style={{
                padding: "8px 0",
                borderBottom: `1px solid ${theme.stroke.tertiary}`,
              }}
            >
              <Row gap={8} align="center" style={{ minWidth: 0 }}>
                <Text size="small" tone="tertiary">
                  {index + 1}
                </Text>
                <Text truncate>
                  {row.webUrl ? (
                    <Link href={row.webUrl}>{row.label}</Link>
                  ) : (
                    row.label
                  )}{" "}
                  · {row.title}
                </Text>
              </Row>
              <Row gap={12} align="center">
                <Text size="small" tone="secondary">
                  {row.mean.toLocaleString(undefined, {
                    maximumFractionDigits: 2,
                  })}{" "}
                  {unit}
                </Text>
                <Text
                  as="span"
                  weight="semibold"
                  style={{
                    minWidth: 64,
                    textAlign: "right",
                    color:
                      row.pctBetter >= 0
                        ? theme.category.green
                        : theme.category.red,
                  }}
                >
                  {row.pctBetter > 0 ? "+" : ""}
                  {row.pctBetter.toFixed(1)}%
                </Text>
              </Row>
            </Row>
          </div>
        ))}
      </Stack>
      <Text size="small" tone="tertiary">
        Best first by {metric} mean. Percent is mean vs baseline {baselineSha},
        not an experiment verdict. Source: {source}.
      </Text>
    </Stack>
  );
}
