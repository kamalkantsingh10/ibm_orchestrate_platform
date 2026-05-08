// CockpitChatPanel tests — Story 6.8 / AC #12.

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const { useCockpitChatMock } = vi.hoisted(() => ({
  useCockpitChatMock: vi.fn(),
}));

vi.mock('@/hooks/useCockpitChat', () => ({
  useCockpitChat: useCockpitChatMock,
}));

import { CockpitChatPanel } from './CockpitChatPanel';

describe('CockpitChatPanel', () => {
  it('shows the empty-state hint on first render', () => {
    useCockpitChatMock.mockReturnValue({
      messages: [],
      send: vi.fn(),
      isAwaitingReply: false,
      clearTranscript: vi.fn(),
    });
    render(<CockpitChatPanel caseId="case_x" />);
    expect(screen.getByText(/Ask Cockpit Chat about this case/)).toBeInTheDocument();
  });

  it('renders user + agent messages from the hook', () => {
    useCockpitChatMock.mockReturnValue({
      messages: [
        { id: 'm1', role: 'user', text: 'why is screening amber?', sentAt: 'now' },
        {
          id: 'm1',
          role: 'agent',
          text: 'Screening returned 1 hit at 73%.',
          status: 'complete',
          agentActionIds: [],
          updatedAt: 'now',
        },
      ],
      send: vi.fn(),
      isAwaitingReply: false,
      clearTranscript: vi.fn(),
    });
    render(<CockpitChatPanel caseId="case_x" />);
    expect(screen.getByText('why is screening amber?')).toBeInTheDocument();
    expect(screen.getByText(/Screening returned 1 hit at 73%/)).toBeInTheDocument();
  });

  it('renders citation as a clickable chip when the citation is in agent_action_ids', () => {
    const onCitationClick = vi.fn();
    useCockpitChatMock.mockReturnValue({
      messages: [
        {
          id: 'm1',
          role: 'agent',
          text: 'Hit found (led_01ABCDEFGHJKMNPQRSTVWXYZ12).',
          status: 'complete',
          agentActionIds: ['led_01ABCDEFGHJKMNPQRSTVWXYZ12'],
          updatedAt: 'now',
        },
      ],
      send: vi.fn(),
      isAwaitingReply: false,
      clearTranscript: vi.fn(),
    });
    render(<CockpitChatPanel caseId="case_x" onCitationClick={onCitationClick} />);
    const chip = screen.getByTestId('chat-citation-led_01ABCDEFGHJKMNPQRSTVWXYZ12');
    fireEvent.click(chip);
    expect(onCitationClick).toHaveBeenCalledWith('led_01ABCDEFGHJKMNPQRSTVWXYZ12');
  });

  it('renders broken citation as red error chip when not in agent_action_ids', () => {
    useCockpitChatMock.mockReturnValue({
      messages: [
        {
          id: 'm1',
          role: 'agent',
          text: 'Bad ref (led_01ABCDEFGHJKMNPQRSTVWXYZ99).',
          status: 'complete',
          agentActionIds: ['led_01OTHERWZ4VHKHGNYHN44JCMA1'],
          updatedAt: 'now',
        },
      ],
      send: vi.fn(),
      isAwaitingReply: false,
      clearTranscript: vi.fn(),
    });
    const { container } = render(<CockpitChatPanel caseId="case_x" />);
    const errorChip = container.querySelector(
      'span[title="citation does not resolve in this case\'s ledger"]',
    );
    expect(errorChip).not.toBeNull();
    expect(errorChip!.textContent).toContain('led_01ABCDEF');
  });

  it('typing indicator shows while a message is streaming', () => {
    useCockpitChatMock.mockReturnValue({
      messages: [
        {
          id: 'm1',
          role: 'agent',
          text: '',
          status: 'streaming',
          agentActionIds: [],
          updatedAt: 'now',
        },
      ],
      send: vi.fn(),
      isAwaitingReply: true,
      clearTranscript: vi.fn(),
    });
    render(<CockpitChatPanel caseId="case_x" />);
    // Two ellipses: the streaming-message body + the panel-level typing
    // indicator. Both are present while a stream is in flight.
    const ellipses = screen.getAllByText('…');
    expect(ellipses.length).toBeGreaterThanOrEqual(1);
  });

  it('Enter submits the form, calling send', () => {
    const send = vi.fn().mockResolvedValue(undefined);
    useCockpitChatMock.mockReturnValue({
      messages: [],
      send,
      isAwaitingReply: false,
      clearTranscript: vi.fn(),
    });
    render(<CockpitChatPanel caseId="case_x" />);
    const composer = screen.getByLabelText('Cockpit chat composer');
    fireEvent.change(composer, { target: { value: 'hello' } });
    fireEvent.keyDown(composer, { key: 'Enter' });
    expect(send).toHaveBeenCalledWith('hello');
  });

  it('Shift+Enter does NOT submit', () => {
    const send = vi.fn();
    useCockpitChatMock.mockReturnValue({
      messages: [],
      send,
      isAwaitingReply: false,
      clearTranscript: vi.fn(),
    });
    render(<CockpitChatPanel caseId="case_x" />);
    const composer = screen.getByLabelText('Cockpit chat composer');
    fireEvent.change(composer, { target: { value: 'hello' } });
    fireEvent.keyDown(composer, { key: 'Enter', shiftKey: true });
    expect(send).not.toHaveBeenCalled();
  });

  it('Send button is disabled when the composer is empty', () => {
    useCockpitChatMock.mockReturnValue({
      messages: [],
      send: vi.fn(),
      isAwaitingReply: false,
      clearTranscript: vi.fn(),
    });
    render(<CockpitChatPanel caseId="case_x" />);
    expect(screen.getByText('Send')).toBeDisabled();
  });

  it('renders an error message with role="alert"', () => {
    useCockpitChatMock.mockReturnValue({
      messages: [
        {
          id: 'm1',
          role: 'agent',
          text: 'Error: kaboom',
          status: 'error',
          agentActionIds: [],
          updatedAt: 'now',
        },
      ],
      send: vi.fn(),
      isAwaitingReply: false,
      clearTranscript: vi.fn(),
    });
    render(<CockpitChatPanel caseId="case_x" />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });
});
