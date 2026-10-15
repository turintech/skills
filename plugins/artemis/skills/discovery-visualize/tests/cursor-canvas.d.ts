declare module "cursor/canvas" {
  type Children = unknown;
  type Style = Record<string, string | number | undefined>;

  export function H1(props: { children?: Children; style?: Style }): JSX.Element;
  export function H2(props: { children?: Children; style?: Style }): JSX.Element;
  export function Text(props: {
    children?: Children;
    tone?: string;
    size?: string;
    as?: string;
    weight?: string;
    truncate?: boolean | string;
    style?: Style;
  }): JSX.Element;
  export function Link(props: {
    children?: Children;
    href: string;
    style?: Style;
  }): JSX.Element;
  export function Stack(props: {
    children?: Children;
    gap?: number;
    style?: Style;
  }): JSX.Element;
  export function Row(props: {
    children?: Children;
    gap?: number;
    align?: string;
    justify?: string;
    wrap?: boolean;
    style?: Style;
  }): JSX.Element;
  export function Stat(props: {
    value: Children;
    label: string;
    tone?: string;
    style?: Style;
  }): JSX.Element;
  export function Callout(props: {
    children?: Children;
    tone?: string;
    title?: Children;
  }): JSX.Element;
  export function Card(props: {
    children?: Children;
    collapsible?: boolean;
    open?: boolean;
    onOpenChange?: (open: boolean) => void;
  }): JSX.Element;
  export function CardHeader(props: {
    children?: Children;
    trailing?: Children;
  }): JSX.Element;
  export function CardBody(props: { children?: Children }): JSX.Element;
  export function UsageBar(props: {
    segments: Array<{ id: string; value: number }>;
    total: number;
    topLeftLabel?: Children;
    topRightLabel?: Children;
  }): JSX.Element;
  export function LineChart(props: {
    categories: string[];
    series: Array<{ name: string; data: number[]; tone?: string }>;
    valueSuffix?: string;
    beginAtZero?: boolean;
    referenceLines?: Array<{ value: number; label?: string }>;
    height?: number;
  }): JSX.Element;
  export function useHostTheme(): {
    text: Record<string, string>;
    bg: Record<string, string>;
    fill: Record<string, string>;
    stroke: Record<string, string>;
    accent: Record<string, string>;
    category: Record<string, string>;
  };
  export function useCanvasState<T>(
    key: string,
    defaultValue: T,
  ): [T, (value: T | ((prev: T) => T)) => void];
  export function computeDAGLayout(options: {
    nodes: Array<{ id: string }>;
    edges: Array<{ from: string; to: string }>;
    direction?: "vertical" | "horizontal";
    nodeWidth?: number;
    nodeHeight?: number;
    rankGap?: number;
    nodeGap?: number;
    padding?: number;
  }): {
    width: number;
    height: number;
    nodes: Array<{ id: string; x: number; y: number }>;
    edges: Array<{
      from: string;
      to: string;
      sourceX: number;
      sourceY: number;
      targetX: number;
      targetY: number;
      isBackEdge?: boolean;
    }>;
  };
}
