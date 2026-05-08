// DeferPopover tests — Story 4.2 AC #9.

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DeferPopover } from './DeferPopover';
import { useDeferredFilter } from '@/stores/deferredFilterStore';

describe('DeferPopover', () => {
  beforeEach(() => {
    useDeferredFilter.getState().reset();
  });

  it('renders three radio defer options + Cancel when open', () => {
    render(
      <DeferPopover open onOpenChange={() => {}} caseId="case_1" caseName="Acme" anchor={null} />,
    );
    expect(screen.getByRole('radio', { name: /defer 1 hour/i })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /defer until tomorrow 9 am/i })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /defer 7 days/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
  });

  it('selecting an option writes a future ISO into the deferred store and closes', async () => {
    const onOpenChange = vi.fn();
    render(
      <DeferPopover
        open
        onOpenChange={onOpenChange}
        caseId="case_1"
        caseName="Acme"
        anchor={null}
      />,
    );
    const user = userEvent.setup();
    await user.click(screen.getByRole('radio', { name: /defer 1 hour/i }));
    const iso = useDeferredFilter.getState().deferUntilByCaseId['case_1'];
    expect(iso).toBeDefined();
    expect(new Date(iso).getTime()).toBeGreaterThan(Date.now());
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it('Cancel closes without writing', async () => {
    const onOpenChange = vi.fn();
    render(
      <DeferPopover
        open
        onOpenChange={onOpenChange}
        caseId="case_1"
        caseName="Acme"
        anchor={null}
      />,
    );
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /cancel/i }));
    expect(useDeferredFilter.getState().deferUntilByCaseId).toEqual({});
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it('does nothing when caseId is null', async () => {
    render(
      <DeferPopover open onOpenChange={() => {}} caseId={null} caseName={null} anchor={null} />,
    );
    const user = userEvent.setup();
    await user.click(screen.getByRole('radio', { name: /defer 1 hour/i }));
    expect(useDeferredFilter.getState().deferUntilByCaseId).toEqual({});
  });
});
