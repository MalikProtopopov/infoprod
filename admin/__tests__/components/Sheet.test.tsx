import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { Sheet, Button } from '@/components/ui';

describe('Sheet', () => {
  it('renders nothing when open is false', () => {
    render(
      <Sheet open={false} onClose={() => {}} title="Hidden">
        <div>content</div>
      </Sheet>,
    );
    expect(screen.queryByText('Hidden')).not.toBeInTheDocument();
  });

  it('renders title and children when open', () => {
    render(
      <Sheet open onClose={() => {}} title="My Sheet">
        <div>body text</div>
      </Sheet>,
    );
    expect(screen.getByText('My Sheet')).toBeInTheDocument();
    expect(screen.getByText('body text')).toBeInTheDocument();
  });

  it('renders description when provided', () => {
    render(
      <Sheet open onClose={() => {}} title="T" description="explanation here">
        <div>x</div>
      </Sheet>,
    );
    expect(screen.getByText('explanation here')).toBeInTheDocument();
  });

  it('renders footer when provided', () => {
    render(
      <Sheet open onClose={() => {}} title="T" footer={<Button>OK</Button>}>
        <div>x</div>
      </Sheet>,
    );
    expect(screen.getByRole('button', { name: 'OK' })).toBeInTheDocument();
  });

  it('calls onClose when ✕ clicked', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <Sheet open onClose={onClose} title="T">
        <div>x</div>
      </Sheet>,
    );
    await user.click(screen.getByLabelText('Закрыть'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('calls onClose when Escape pressed', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <Sheet open onClose={onClose} title="T">
        <div>x</div>
      </Sheet>,
    );
    await user.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('blocks body scroll while open', () => {
    const { rerender } = render(
      <Sheet open onClose={() => {}} title="T">
        <div>x</div>
      </Sheet>,
    );
    expect(document.body.style.overflow).toBe('hidden');
    rerender(
      <Sheet open={false} onClose={() => {}} title="T">
        <div>x</div>
      </Sheet>,
    );
    // После закрытия overflow должен быть восстановлен
    expect(document.body.style.overflow).not.toBe('hidden');
  });
});
