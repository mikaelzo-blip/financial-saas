/**
 * Utilities for formatting and parsing Indonesian currency inputs.
 */

/**
 * Formats a raw numeric string or number into Indonesian dot-separated format.
 * e.g. "1200000000" -> "1.200.000.000"
 */
export function formatCurrencyInput(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === '') return '';
  const digits = String(value).replace(/\D/g, '');
  if (!digits) return '';
  const cleanDigits = digits.replace(/^0+(?=\d)/, '');
  return cleanDigits.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
}

/**
 * Parses a formatted Indonesian currency string into a clean numeric string.
 * e.g. "1.200.000.000" -> "1200000000"
 * e.g. "Rp 1.200.000.000" -> "1200000000"
 */
export function parseCurrencyInput(value: string | null | undefined): string {
  if (!value) return '';
  const digits = value.replace(/\D/g, '');
  return digits.replace(/^0+(?=\d)/, '');
}

/**
 * Calculates new cursor position after re-formatting input text.
 */
export function computeCursorPosition(
  rawInput: string,
  rawCursor: number,
  formattedText: string
): number {
  const digitsBefore = rawInput.slice(0, rawCursor).replace(/\D/g, '').length;
  if (digitsBefore === 0) return 0;
  let count = 0;
  for (let i = 0; i < formattedText.length; i++) {
    if (/\d/.test(formattedText[i])) {
      count++;
      if (count === digitsBefore) {
        return i + 1;
      }
    }
  }
  return formattedText.length;
}
