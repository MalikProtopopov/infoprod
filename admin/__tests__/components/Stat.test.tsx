import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Stat } from '@/components/ui';

describe('Stat', () => {
  it('renders label and value', () => {
    render(<Stat label="Active" value={42} />);
    expect(screen.getByText('Active')).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
  });

  it('renders hint when provided', () => {
    render(<Stat label="X" value={1} hint="extra context" />);
    expect(screen.getByText('extra context')).toBeInTheDocument();
  });

  it('renders icon when provided', () => {
    render(
      <Stat label="X" value={1} icon={<svg data-testid="icon" />} />,
    );
    expect(screen.getByTestId('icon')).toBeInTheDocument();
  });

  it.each(['indigo', 'violet', 'rose', 'teal', 'amber'] as const)(
    'accepts accent="%s"',
    (accent) => {
      render(<Stat label="X" value={1} accent={accent} icon={<svg />} />);
      expect(screen.getByText('X')).toBeInTheDocument();
    },
  );

  it('renders string value', () => {
    render(<Stat label="Revenue" value="120 000 ₽" />);
    expect(screen.getByText('120 000 ₽')).toBeInTheDocument();
  });
});
