// sse.ts tests — Story 4.6 AC #12.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient } from '@tanstack/react-query';
import { subscribeToCase } from './sse';

class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  listeners: Record<string, ((e: MessageEvent) => void)[]> = {};
  closed = false;
  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }
  addEventListener(name: string, cb: (e: MessageEvent) => void): void {
    (this.listeners[name] ??= []).push(cb);
  }
  fire(name: string, data: unknown = {}): void {
    const evt = new MessageEvent(name, { data: JSON.stringify(data) });
    for (const cb of this.listeners[name] ?? []) cb(evt);
  }
  close(): void {
    this.closed = true;
  }
}

function makeQueryClientWithSpy(): {
  qc: QueryClient;
  invalidate: ReturnType<typeof vi.fn>;
} {
  const qc = new QueryClient();
  const invalidate = vi.fn();
  // Patch the method so we can assert on call shape; preserve original
  // resolution for any internal pathway.
  qc.invalidateQueries = ((opts: unknown) => {
    invalidate(opts);
    return Promise.resolve();
  }) as typeof qc.invalidateQueries;
  return { qc, invalidate };
}

describe('subscribeToCase', () => {
  beforeEach(() => {
    MockEventSource.instances = [];
  });
  afterEach(() => {
    MockEventSource.instances = [];
  });

  it('opens an EventSource against the case stream URL with the user id', () => {
    const { qc } = makeQueryClientWithSpy();
    subscribeToCase('case_X', 'user-1', qc, {
      EventSourceCtor: MockEventSource as unknown as typeof EventSource,
    });
    expect(MockEventSource.instances).toHaveLength(1);
    expect(MockEventSource.instances[0]!.url).toBe('/v1/cases/case_X/stream?as=user-1');
  });

  it('agent.state_changed → invalidates agent-mesh-state', () => {
    const { qc, invalidate } = makeQueryClientWithSpy();
    subscribeToCase('case_X', 'user-1', qc, {
      EventSourceCtor: MockEventSource as unknown as typeof EventSource,
    });
    MockEventSource.instances[0]!.fire('agent.state_changed');
    expect(invalidate).toHaveBeenCalledWith({
      queryKey: ['cases', 'case_X', 'agent-mesh-state'],
    });
  });

  it('case.state_changed → invalidates [case, caseId] AND [cases]', () => {
    const { qc, invalidate } = makeQueryClientWithSpy();
    subscribeToCase('case_X', 'user-1', qc, {
      EventSourceCtor: MockEventSource as unknown as typeof EventSource,
    });
    MockEventSource.instances[0]!.fire('case.state_changed');
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['case', 'case_X'] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['cases'] });
  });

  it('case.documents_changed → invalidates intake + case', () => {
    const { qc, invalidate } = makeQueryClientWithSpy();
    subscribeToCase('case_X', 'user-1', qc, {
      EventSourceCtor: MockEventSource as unknown as typeof EventSource,
    });
    MockEventSource.instances[0]!.fire('case.documents_changed');
    expect(invalidate).toHaveBeenCalledWith({
      queryKey: ['cases', 'case_X', 'intake', 'document_intelligence'],
    });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['case', 'case_X'] });
  });

  it('returned unsubscribe closes the EventSource', () => {
    const { qc } = makeQueryClientWithSpy();
    const unsub = subscribeToCase('case_X', 'user-1', qc, {
      EventSourceCtor: MockEventSource as unknown as typeof EventSource,
    });
    unsub();
    expect(MockEventSource.instances[0]!.closed).toBe(true);
  });
});
