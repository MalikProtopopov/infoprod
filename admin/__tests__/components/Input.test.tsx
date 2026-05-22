import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { Input, Textarea, Select } from '@/components/ui';

describe('Input', () => {
  it('renders', () => {
    render(<Input placeholder="enter" />);
    expect(screen.getByPlaceholderText('enter')).toBeInTheDocument();
  });

  it('accepts user input', async () => {
    const user = userEvent.setup();
    render(<Input placeholder="x" />);
    const el = screen.getByPlaceholderText('x') as HTMLInputElement;
    await user.type(el, 'hello');
    expect(el.value).toBe('hello');
  });

  it('forwards onChange', async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<Input onChange={onChange} placeholder="x" />);
    await user.type(screen.getByPlaceholderText('x'), 'a');
    expect(onChange).toHaveBeenCalled();
  });

  it('passes className', () => {
    const { container } = render(<Input className="my-cls" />);
    expect(container.querySelector('input')?.className).toContain('my-cls');
  });
});

describe('Textarea', () => {
  it('renders and accepts input', async () => {
    const user = userEvent.setup();
    render(<Textarea placeholder="x" rows={3} />);
    const el = screen.getByPlaceholderText('x') as HTMLTextAreaElement;
    await user.type(el, 'line');
    expect(el.value).toBe('line');
  });
});

describe('Select', () => {
  it('renders options', () => {
    render(
      <Select defaultValue="a">
        <option value="a">A</option>
        <option value="b">B</option>
      </Select>,
    );
    expect(screen.getByText('A')).toBeInTheDocument();
    expect(screen.getByText('B')).toBeInTheDocument();
  });
});
