declare namespace JSX {
  interface Element {}
  interface IntrinsicElements {
    [element: string]: any;
  }
}

declare module "react" {
  export type CSSProperties = Record<string, string | number | undefined>;
  export type ReactNode = unknown;

  export namespace JSX {
    interface Element {}
    interface IntrinsicElements {
      [element: string]: any;
    }
  }
}

declare module "react/jsx-runtime" {
  export const Fragment: unknown;
  export function jsx(type: unknown, props: unknown, key?: unknown): unknown;
  export function jsxs(type: unknown, props: unknown, key?: unknown): unknown;

  export namespace JSX {
    interface Element {}
    interface IntrinsicElements {
      [element: string]: any;
    }
  }
}
