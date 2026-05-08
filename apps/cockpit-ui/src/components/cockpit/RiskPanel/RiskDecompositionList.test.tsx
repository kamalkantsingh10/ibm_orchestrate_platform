import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import voraScore from '../RiskScoreBar/__fixtures__/vora-risk-score.json';
import { RiskDecompositionList, type RiskComponent } from './RiskDecompositionList';

const components = (voraScore as { components: RiskComponent[] }).components;

describe('RiskDecompositionList', () => {
  it('renders one row per component', () => {
    render(<RiskDecompositionList components={components} />);
    expect(screen.getByTestId('risk-decomposition-country')).toBeInTheDocument();
    expect(screen.getByTestId('risk-decomposition-entity_type')).toBeInTheDocument();
    expect(screen.getByTestId('risk-decomposition-ownership_clarity')).toBeInTheDocument();
    expect(screen.getByTestId('risk-decomposition-screening')).toBeInTheDocument();
    expect(screen.getByTestId('risk-decomposition-adverse_media')).toBeInTheDocument();
  });

  it('shows the rationale text for each component', () => {
    render(<RiskDecompositionList components={components} />);
    expect(
      screen.getByText(/3 nominee-suspected edge\(s\); 0 officer-corrected edge\(s\)/i),
    ).toBeInTheDocument();
  });
});
