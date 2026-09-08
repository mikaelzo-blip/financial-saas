import { describe, expect, it } from 'vitest';
import { formatIDR } from '../../src/utils/formatters';

describe('formatIDR', () => {
  it('omits decimals for whole Rupiah values', () => {
    expect(formatIDR('108000000.00')).toBe('Rp 108.000.000');
    expect(formatIDR(0)).toBe('Rp 0');
  });

  it('keeps decimal precision when the value contains sen', () => {
    expect(formatIDR('108000000.25')).toBe('Rp 108.000.000,25');
  });
});
