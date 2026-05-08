// AgentFace tests — Story 4.3 AC #6.

import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AgentFace, type AgentFaceState } from './AgentFace';

const STATES: AgentFaceState[] = ['idle', 'working', 'complete', 'blocked', 'needs_input'];

describe('AgentFace', () => {
  it.each(STATES)('renders for state=%s with the right data-state', (state) => {
    render(<AgentFace agent="document-intelligence" state={state} />);
    const node = screen.getByRole('img');
    expect(node).toHaveAttribute('data-state', state);
    expect(node).toHaveAttribute('data-agent', 'document-intelligence');
  });

  it('renders the default size of 32×32', () => {
    render(<AgentFace agent="case-supervisor" state="idle" />);
    const node = screen.getByRole('img');
    expect(node).toHaveStyle({ width: '32px', height: '32px' });
  });

  it('honors the size prop', () => {
    render(<AgentFace agent="case-supervisor" state="idle" size={48} />);
    const node = screen.getByRole('img');
    expect(node).toHaveStyle({ width: '48px', height: '48px' });
  });

  it('default aria-label combines agent label and state', () => {
    render(<AgentFace agent="document-intelligence" state="working" />);
    expect(screen.getByLabelText('Document Intelligence — Working')).toBeInTheDocument();
  });

  it('explicit aria-label wins', () => {
    render(<AgentFace agent="document-intelligence" state="working" aria-label="DocAI is busy" />);
    expect(screen.getByLabelText('DocAI is busy')).toBeInTheDocument();
  });

  it('blocked state renders the AlertTriangle overlay', () => {
    render(<AgentFace agent="screening" state="blocked" />);
    expect(screen.getByTestId('agent-face-blocked-overlay')).toBeInTheDocument();
  });

  it('non-blocked states do NOT render the overlay', () => {
    render(<AgentFace agent="screening" state="idle" />);
    expect(screen.queryByTestId('agent-face-blocked-overlay')).not.toBeInTheDocument();
  });

  it('embeds the agent SVG via /agent-faces/<slug>.svg', () => {
    const { container } = render(<AgentFace agent="ubo-graph" state="idle" />);
    const img = container.querySelector('img');
    expect(img).toHaveAttribute('src', '/agent-faces/ubo-graph.svg');
  });
});
