import React, { forwardRef, useImperativeHandle, useRef } from 'react';
import { Input, InputProps } from './Input';
import { computeCursorPosition, formatCurrencyInput, parseCurrencyInput } from '../../utils/currency';

export interface CurrencyInputProps extends Omit<InputProps, 'value' | 'onChange' | 'type'> {
  value: number | string | null | undefined;
  onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onValueChange?: (numericString: string, numericValue: number | null) => void;
}

export const CurrencyInput = forwardRef<HTMLInputElement, CurrencyInputProps>(
  ({ value, onChange, onValueChange, placeholder = '0', leftAddon, ...props }, ref) => {
    const internalRef = useRef<HTMLInputElement>(null);
    useImperativeHandle(ref, () => internalRef.current as HTMLInputElement);

    const formattedValue = formatCurrencyInput(value);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const rawInput = e.target.value;
      const rawCursor = e.target.selectionStart ?? rawInput.length;
      const cleanDigits = parseCurrencyInput(rawInput);
      const newFormatted = formatCurrencyInput(cleanDigits);
      const nextCursor = computeCursorPosition(rawInput, rawCursor, newFormatted);

      // Re-target synthetic event value to clean digits for state handlers
      const syntheticEvent = {
        ...e,
        target: {
          ...e.target,
          name: e.target.name,
          value: cleanDigits,
        },
      } as React.ChangeEvent<HTMLInputElement>;

      onChange?.(syntheticEvent);
      onValueChange?.(cleanDigits, cleanDigits ? Number(cleanDigits) : null);

      requestAnimationFrame(() => {
        if (internalRef.current) {
          internalRef.current.setSelectionRange(nextCursor, nextCursor);
        }
      });
    };

    return (
      <Input
        ref={internalRef}
        type="text"
        inputMode="numeric"
        value={formattedValue}
        onChange={handleChange}
        placeholder={placeholder}
        leftAddon={leftAddon || <span className="text-xs font-semibold text-slate-500">Rp</span>}
        {...props}
      />
    );
  }
);

CurrencyInput.displayName = 'CurrencyInput';
