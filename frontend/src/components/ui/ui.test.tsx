import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Panel } from './Panel';
import { SeverityChip } from './SeverityChip';
import { maxBand, bandLabel } from './bandLabel';
import { Drawer } from './Drawer';
import { EmptyState } from './EmptyState';
import { ErrorState } from './ErrorState';
import { StatusDot } from './StatusDot';

describe('ui primitives', () => {
  it('Panel shows title and count', () => {
    render(<Panel title="Live events" count={12}><p>body</p></Panel>);
    expect(screen.getByRole('heading', { name: 'Live events 12' })).toBeInTheDocument();
    expect(screen.getByText('12')).toBeInTheDocument();
  });
  it('SeverityChip renders sentence-case label and data-band', () => {
    render(<SeverityChip band="warning" />);
    const chip = screen.getByText('Warning');
    expect(chip).toHaveAttribute('data-band', 'warning');
  });
  it('bandLabel and maxBand', () => {
    expect(bandLabel('critical')).toBe('Critical');
    expect(maxBand(['normal', 'critical', 'watch'])).toBe('critical');
    expect(maxBand([])).toBe('normal');
  });
  it('Drawer renders when open, closes on Escape and button', () => {
    const onClose = vi.fn();
    const { rerender } = render(<Drawer open={false} title="Why" onClose={onClose}>x</Drawer>);
    expect(screen.queryByRole('dialog')).toBeNull();
    rerender(<Drawer open title="Why" onClose={onClose}>x</Drawer>);
    expect(screen.getByRole('dialog', { name: 'Why' })).toBeInTheDocument();
    fireEvent.keyDown(document, { key: 'Escape' });
    fireEvent.click(screen.getByRole('button', { name: 'Close' }));
    expect(onClose).toHaveBeenCalledTimes(2);
  });
  it('Drawer takes focus while open and gives it back when it closes', () => {
    const { rerender } = render(<><button type="button">Why?</button><Drawer open={false} title="Why" onClose={vi.fn()}>x</Drawer></>);
    const trigger = screen.getByRole('button', { name: 'Why?' });
    trigger.focus();
    rerender(<><button type="button">Why?</button><Drawer open title="Why" onClose={vi.fn()}>x</Drawer></>);
    expect(screen.getByRole('dialog', { name: 'Why' })).toHaveFocus();
    rerender(<><button type="button">Why?</button><Drawer open={false} title="Why" onClose={vi.fn()}>x</Drawer></>);
    expect(trigger).toHaveFocus();
  });
  it('a stacked Drawer sits above the other and takes Escape alone', () => {
    const closeBase = vi.fn();
    const closeTop = vi.fn();
    render(<><Drawer open title="Why" onClose={closeBase}>x</Drawer><Drawer open stacked title="Source" onClose={closeTop}>y</Drawer></>);
    expect(screen.getByRole('dialog', { name: 'Source' })).toHaveClass('z-50');
    expect(screen.getByRole('dialog', { name: 'Why' })).toHaveClass('z-40');
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(closeTop).toHaveBeenCalledTimes(1);
    expect(closeBase).not.toHaveBeenCalled();
  });
  it('EmptyState, ErrorState, StatusDot expose roles and labels', () => {
    const retry = vi.fn();
    render(<><EmptyState title="No incidents" body="Threats appear here." /><ErrorState message="City failed to load" onRetry={retry} /><StatusDot status="running" label="Running" /></>);
    expect(screen.getByRole('note')).toHaveTextContent('No incidents');
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(retry).toHaveBeenCalled();
    expect(screen.getByRole('status')).toHaveTextContent('Running');
  });
});
