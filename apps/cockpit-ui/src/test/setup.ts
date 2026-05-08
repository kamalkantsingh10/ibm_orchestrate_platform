import '@testing-library/jest-dom/vitest';

// jsdom does not implement ResizeObserver. react-flow (Story 5.4 onward)
// uses it to measure the canvas — polyfill with a no-op so component tests
// can mount the <ReactFlow> wrapper.
if (typeof globalThis.ResizeObserver === 'undefined') {
  class ResizeObserverPolyfill {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  }
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (globalThis as any).ResizeObserver = ResizeObserverPolyfill;
}

// jsdom doesn't implement DOMMatrixReadOnly which react-flow uses internally.
if (typeof globalThis.DOMMatrixReadOnly === 'undefined') {
  class DOMMatrixReadOnlyStub {
    a = 1;
    b = 0;
    c = 0;
    d = 1;
    e = 0;
    f = 0;
    constructor() {}
  }
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (globalThis as any).DOMMatrixReadOnly = DOMMatrixReadOnlyStub;
}
