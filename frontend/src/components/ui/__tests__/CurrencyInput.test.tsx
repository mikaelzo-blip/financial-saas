import { useState } from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CurrencyInput } from '../CurrencyInput';
import { formatCurrencyInput, parseCurrencyInput } from '../../../utils/currency';

describe('currency utilities', () => {
  it('formats raw numeric strings to Indonesian dot-separated format', () => {
    expect(formatCurrencyInput('1200000000')).toBe('1.200.000.000');
    expect(formatCurrencyInput(1200000000)).toBe('1.200.000.000');
    expect(formatCurrencyInput('120000000')).toBe('120.000.000');
    expect(formatCurrencyInput('500000')).toBe('500.000');
    expect(formatCurrencyInput('')).toBe('');
    expect(formatCurrencyInput(null)).toBe('');
    expect(formatCurrencyInput(undefined)).toBe('');
  });

  it('parses formatted Indonesian currency strings to clean numeric strings', () => {
    expect(parseCurrencyInput('1.200.000.000')).toBe('1200000000');
    expect(parseCurrencyInput('Rp 1.200.000.000')).toBe('1200000000');
    expect(parseCurrencyInput('Rp. 120.000.000')).toBe('120000000');
    expect(parseCurrencyInput('abc 500.000 xyz')).toBe('500000');
    expect(parseCurrencyInput('')).toBe('');
  });
});

describe('CurrencyInput Component', () => {
  it('renders initial formatted value with Rp prefix', () => {
    render(<CurrencyInput label="Nilai Kontrak" value="1200000000" onChange={() => {}} />);
    const input = screen.getByRole('textbox', { name: /nilai kontrak/i }) as HTMLInputElement;
    expect(input.value).toBe('1.200.000.000');
    expect(screen.getByText('Rp')).toBeInTheDocument();
  });

  it('updates formatted text and calls onChange with raw numeric string when typing', async () => {
    const user = userEvent.setup();
    const handleChange = vi.fn();

    function Wrapper() {
      const [val, setVal] = useState('');
      return (
        <CurrencyInput
          label="Nominal Transaksi"
          value={val}
          onChange={(e) => {
            setVal(e.target.value);
            handleChange(e.target.value);
          }}
        />
      );
    }

    render(<Wrapper />);
    const input = screen.getByRole('textbox', { name: /nominal transaksi/i }) as HTMLInputElement;

    await user.type(input, '15000000');

    expect(input.value).toBe('15.000.000');
    expect(handleChange).toHaveBeenLastCalledWith('15000000');
  });

  it('supports backspace and deletion smoothly', async () => {
    const user = userEvent.setup();

    function Wrapper() {
      const [val, setVal] = useState('1000000');
      return (
        <CurrencyInput
          label="Nominal"
          value={val}
          onChange={(e) => setVal(e.target.value)}
        />
      );
    }

    render(<Wrapper />);
    const input = screen.getByRole('textbox', { name: /nominal/i }) as HTMLInputElement;
    expect(input.value).toBe('1.000.000');

    await user.type(input, '{backspace}');
    expect(input.value).toBe('100.000');

    await user.type(input, '{backspace}');
    expect(input.value).toBe('10.000');
  });

  it('strips non-numeric characters automatically', async () => {
    const user = userEvent.setup();

    function Wrapper() {
      const [val, setVal] = useState('');
      return (
        <CurrencyInput
          label="Nominal"
          value={val}
          onChange={(e) => setVal(e.target.value)}
        />
      );
    }

    render(<Wrapper />);
    const input = screen.getByRole('textbox', { name: /nominal/i }) as HTMLInputElement;

    await user.type(input, 'abc120def000');
    expect(input.value).toBe('120.000');
  });
});
