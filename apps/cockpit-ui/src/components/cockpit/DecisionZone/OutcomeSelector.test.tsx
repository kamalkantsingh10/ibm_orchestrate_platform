// OutcomeSelector tests — Story 7.9 / AC #9.

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { OutcomeSelector } from './OutcomeSelector';

describe('OutcomeSelector', () => {
  it('renders four outcome options plus a placeholder', () => {
    render(
      <OutcomeSelector
        outcome={null}
        conditions={[]}
        onOutcomeChange={() => {}}
        onConditionsChange={() => {}}
      />,
    );
    const select = screen.getByLabelText('Decision outcome') as HTMLSelectElement;
    expect(Array.from(select.querySelectorAll('option')).map((o) => o.value)).toEqual([
      '',
      'approve',
      'decline',
      'approve_with_conditions',
      'escalate_to_edd',
    ]);
  });

  it('selecting approve_with_conditions reveals the conditions editor', () => {
    render(
      <OutcomeSelector
        outcome="approve_with_conditions"
        conditions={[]}
        onOutcomeChange={() => {}}
        onConditionsChange={() => {}}
      />,
    );
    expect(screen.getByTestId('outcome-selector-conditions')).toBeInTheDocument();
    expect(screen.getByLabelText('Add condition')).toBeInTheDocument();
  });

  it('selecting escalate_to_edd shows the escalation hint', () => {
    render(
      <OutcomeSelector
        outcome="escalate_to_edd"
        conditions={[]}
        onOutcomeChange={() => {}}
        onConditionsChange={() => {}}
      />,
    );
    expect(screen.getByText(/Team Lead's approval queue/i)).toBeInTheDocument();
  });

  it('switching away from approve_with_conditions clears conditions', () => {
    const onOutcomeChange = vi.fn();
    const onConditionsChange = vi.fn();
    render(
      <OutcomeSelector
        outcome="approve_with_conditions"
        conditions={['enhanced monitoring']}
        onOutcomeChange={onOutcomeChange}
        onConditionsChange={onConditionsChange}
      />,
    );
    fireEvent.change(screen.getByLabelText('Decision outcome'), {
      target: { value: 'approve' },
    });
    expect(onOutcomeChange).toHaveBeenCalledWith('approve');
    expect(onConditionsChange).toHaveBeenCalledWith([]);
  });

  it('Enter on the conditions input creates a chip', () => {
    const onConditionsChange = vi.fn();
    render(
      <OutcomeSelector
        outcome="approve_with_conditions"
        conditions={[]}
        onOutcomeChange={() => {}}
        onConditionsChange={onConditionsChange}
      />,
    );
    const input = screen.getByLabelText('Add condition');
    fireEvent.change(input, { target: { value: 'enhanced monitoring' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onConditionsChange).toHaveBeenCalledWith(['enhanced monitoring']);
  });

  it('removes a chip when its X button is clicked', () => {
    const onConditionsChange = vi.fn();
    render(
      <OutcomeSelector
        outcome="approve_with_conditions"
        conditions={['a', 'b', 'c']}
        onOutcomeChange={() => {}}
        onConditionsChange={onConditionsChange}
      />,
    );
    fireEvent.click(screen.getByLabelText('Remove condition b'));
    expect(onConditionsChange).toHaveBeenCalledWith(['a', 'c']);
  });

  it('disables the input when 10 conditions are present', () => {
    render(
      <OutcomeSelector
        outcome="approve_with_conditions"
        conditions={['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j']}
        onOutcomeChange={() => {}}
        onConditionsChange={() => {}}
      />,
    );
    const input = screen.getByLabelText('Add condition') as HTMLInputElement;
    expect(input).toBeDisabled();
    expect(input.placeholder).toBe('Max 10 conditions');
  });

  it('rejects whitespace-only conditions', () => {
    const onConditionsChange = vi.fn();
    render(
      <OutcomeSelector
        outcome="approve_with_conditions"
        conditions={[]}
        onOutcomeChange={() => {}}
        onConditionsChange={onConditionsChange}
      />,
    );
    const input = screen.getByLabelText('Add condition');
    fireEvent.change(input, { target: { value: '    ' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onConditionsChange).not.toHaveBeenCalled();
  });

  it('disabled mode renders chips read-only with no input', () => {
    render(
      <OutcomeSelector
        outcome="approve_with_conditions"
        conditions={['enhanced monitoring']}
        onOutcomeChange={() => {}}
        onConditionsChange={() => {}}
        disabled
      />,
    );
    expect(screen.queryByLabelText('Add condition')).toBeNull();
    expect(screen.queryByLabelText('Remove condition enhanced monitoring')).toBeNull();
    expect(screen.getByLabelText('Decision outcome')).toBeDisabled();
  });

  it('Backspace on empty input removes the last chip', () => {
    const onConditionsChange = vi.fn();
    render(
      <OutcomeSelector
        outcome="approve_with_conditions"
        conditions={['a', 'b']}
        onOutcomeChange={() => {}}
        onConditionsChange={onConditionsChange}
      />,
    );
    const input = screen.getByLabelText('Add condition');
    fireEvent.keyDown(input, { key: 'Backspace' });
    expect(onConditionsChange).toHaveBeenCalledWith(['a']);
  });

  it('comma key submits a chip mid-input', () => {
    const onConditionsChange = vi.fn();
    render(
      <OutcomeSelector
        outcome="approve_with_conditions"
        conditions={[]}
        onOutcomeChange={() => {}}
        onConditionsChange={onConditionsChange}
      />,
    );
    const input = screen.getByLabelText('Add condition');
    fireEvent.change(input, { target: { value: 'enhanced monitoring' } });
    fireEvent.keyDown(input, { key: ',' });
    expect(onConditionsChange).toHaveBeenCalledWith(['enhanced monitoring']);
  });
});
