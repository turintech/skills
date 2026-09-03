import {
  Card,
  CardBody,
  CardHeader,
  H2,
  Link,
  Stack,
  Text,
  useCanvasState,
  useHostTheme,
} from "cursor/canvas";

/**
 * Answers: "What was each version trying to do, and did the metric improve?"
 * Snapshot inputs: rankings[metric], version URLs, and experiment rationale.
 * Keep performance direction visible before expansion. Parent references use
 * real Link components because rendered text must not expose Markdown syntax.
 */
export type VersionCardItem = {
  label: string;
  title: string;
  pctBetter: number;
  webUrl: string;
  intentBeforeParent: string;
  parent?: { label: string; webUrl: string };
  intentAfterParent?: string;
};

export type VersionCardsProps = {
  metric: string;
  versions: VersionCardItem[];
  defaultOpenLabel?: string;
};

export function VersionCards({
  metric,
  versions,
  defaultOpenLabel = "",
}: VersionCardsProps) {
  const theme = useHostTheme();
  const [openLabel, setOpenLabel] = useCanvasState(
    `version-cards-${metric}`,
    defaultOpenLabel,
  );

  if (!versions.length) return null;

  return (
    <Stack gap={8}>
      <H2>Version intent and measured outcome</H2>
      {versions.map((version) => (
        <div key={version.label}>
          <Card
            collapsible
            open={openLabel === version.label}
            onOpenChange={(open) =>
              setOpenLabel(open ? version.label : "")
            }
          >
            <CardHeader
              trailing={
                <Text
                  as="span"
                  weight="semibold"
                  style={{
                    color:
                      version.pctBetter >= 0
                        ? theme.category.green
                        : theme.category.red,
                  }}
                >
                  {version.pctBetter > 0 ? "+" : ""}
                  {version.pctBetter.toFixed(1)}%
                </Text>
              }
            >
              <Link
                href={version.webUrl}
                style={{ color: theme.text.link, fontWeight: 590 }}
              >
                {version.label}
              </Link>{" "}
              · {version.title}
            </CardHeader>
            <CardBody>
              <Text>
                {version.intentBeforeParent}
                {version.parent ? (
                  <Link href={version.parent.webUrl}>
                    {version.parent.label}
                  </Link>
                ) : null}
                {version.intentAfterParent}
              </Text>
            </CardBody>
          </Card>
        </div>
      ))}
      <Text size="small" tone="tertiary">
        Ranked by {metric} mean vs baseline. Green/red indicates measured
        improvement/regression, not experiment validation.
      </Text>
    </Stack>
  );
}
