import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Pill } from '@/components/ui';

describe('Pill', () => {
  it('renders text', () => {
    render(<Pill>active</Pill>);
    expect(screen.getByText('active')).toBeInTheDocument();
  });

  it.each([
    ['green', 'emerald'],
    ['red', 'rose'],
    ['amber', 'amber'],
    ['gray', 'zinc'],
    ['indigo', 'indigo'],
    ['violet', 'violet'],
  ] as const)('applies %s color tokens', (color, expectedToken) => {
    const { container } = render(<Pill color={color}>x</Pill>);
    const span = container.firstChild as HTMLElement;
    expect(span.className).toContain(expectedToken);
  });
});
