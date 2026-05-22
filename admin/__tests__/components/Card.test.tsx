import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Card, PlainCard, Empty, PageHeader, TableHead, TableWrap, Td, Th, Tr } from '@/components/ui';

describe('Card', () => {
  it('renders children', () => {
    render(<Card>hello card</Card>);
    expect(screen.getByText('hello card')).toBeInTheDocument();
  });

  it('applies padding when padded=true', () => {
    const { container } = render(<Card padded>x</Card>);
    expect(container.firstChild?.className).toMatch(/p-5|p-6/);
  });

  it('applies custom className', () => {
    const { container } = render(<Card className="my-extra">x</Card>);
    expect(container.firstChild?.className).toContain('my-extra');
  });
});

describe('PlainCard', () => {
  it('renders', () => {
    render(<PlainCard>plain</PlainCard>);
    expect(screen.getByText('plain')).toBeInTheDocument();
  });
});

describe('Empty', () => {
  it('renders message', () => {
    render(<Empty>Nothing here</Empty>);
    expect(screen.getByText('Nothing here')).toBeInTheDocument();
  });
});

describe('PageHeader', () => {
  it('renders title', () => {
    render(<PageHeader title="My Page" />);
    expect(screen.getByRole('heading', { name: 'My Page' })).toBeInTheDocument();
  });

  it('renders subtitle when provided', () => {
    render(<PageHeader title="T" subtitle="sub text" />);
    expect(screen.getByText('sub text')).toBeInTheDocument();
  });

  it('renders action when provided', () => {
    render(<PageHeader title="T" action={<button>+New</button>} />);
    expect(screen.getByRole('button', { name: '+New' })).toBeInTheDocument();
  });
});

describe('Table helpers', () => {
  it('TableWrap renders children', () => {
    render(<TableWrap><div>x</div></TableWrap>);
    expect(screen.getByText('x')).toBeInTheDocument();
  });

  it('TableHead + Th + Tr + Td render', () => {
    render(
      <table>
        <TableHead>
          <Th>Name</Th>
          <Th>Age</Th>
        </TableHead>
        <tbody>
          <Tr>
            <Td>Alice</Td>
            <Td>30</Td>
          </Tr>
        </tbody>
      </table>,
    );
    expect(screen.getByText('Name')).toBeInTheDocument();
    expect(screen.getByText('Alice')).toBeInTheDocument();
  });
});
