import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Field, Input } from '@/components/ui';

describe('Field', () => {
  it('renders label text', () => {
    render(
      <Field label="Email">
        <Input />
      </Field>,
    );
    expect(screen.getByText('Email')).toBeInTheDocument();
  });

  it('renders hint when provided', () => {
    render(
      <Field label="L" hint="Some help">
        <Input />
      </Field>,
    );
    expect(screen.getByText('Some help')).toBeInTheDocument();
  });

  it('shows required indicator when required=true', () => {
    render(
      <Field label="L" required>
        <Input />
      </Field>,
    );
    expect(screen.getByText('*')).toBeInTheDocument();
  });

  it('does not show required indicator when not set', () => {
    render(
      <Field label="L">
        <Input />
      </Field>,
    );
    expect(screen.queryByText('*')).not.toBeInTheDocument();
  });

  it('associates label with input', () => {
    render(
      <Field label="username">
        <Input placeholder="user" />
      </Field>,
    );
    // label-обёртка автоматически связывает с inner input
    expect(screen.getByText('username').tagName.toLowerCase()).toBe('span');
  });
});
