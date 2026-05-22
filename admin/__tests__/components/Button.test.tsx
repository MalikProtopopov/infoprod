import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { Button } from '@/components/ui';

describe('Button', () => {
  it('renders children text', () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole('button', { name: 'Click me' })).toBeInTheDocument();
  });

  it('calls onClick once when clicked', async () => {
    const onClick = vi.fn();
    const user = userEvent.setup();
    render(<Button onClick={onClick}>Press</Button>);
    await user.click(screen.getByRole('button'));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('does not call onClick when disabled', async () => {
    const onClick = vi.fn();
    const user = userEvent.setup();
    render(
      <Button onClick={onClick} disabled>
        Off
      </Button>,
    );
    await user.click(screen.getByRole('button'));
    expect(onClick).not.toHaveBeenCalled();
  });

  it('applies primary variant by default', () => {
    const { container } = render(<Button>X</Button>);
    expect(container.querySelector('button')?.className).toContain('gradient-primary');
  });

  it.each([
    ['ghost', 'glass-soft'],
    ['danger', 'gradient-danger'],
    ['glass', 'glass'],
  ] as const)('applies %s variant class', (variant, expected) => {
    const { container } = render(<Button variant={variant}>X</Button>);
    expect(container.querySelector('button')?.className).toContain(expected);
  });

  it('respects size prop', () => {
    const { container } = render(<Button size="sm">X</Button>);
    expect(container.querySelector('button')?.className).toContain('h-8');
  });
});
