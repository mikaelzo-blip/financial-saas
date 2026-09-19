import { describe, expect, it } from 'vitest';
import shared from '../../../shared/recording-categories.json';
import { RECORDING_CATEGORIES } from '../../src/utils/recordingCategories';

const sharedEntries = shared as Array<{ value: string; kind: string; requiresProject: boolean }>;

describe('RECORDING_CATEGORIES derives from the shared catalog', () => {
  it('has exactly the shared entries, in the same order', () => {
    expect(RECORDING_CATEGORIES.map((c) => c.value)).toEqual(sharedEntries.map((e) => e.value));
  });

  it('marks exactly the shared categories as project-required', () => {
    const expected = sharedEntries.filter((e) => e.requiresProject).map((e) => e.value);
    const actual = RECORDING_CATEGORIES.filter((c) => c.requiresProject).map((c) => c.value);
    expect(actual).toEqual(expected);
  });

  it('maps each entry to the matching cost/expense field', () => {
    for (const entry of sharedEntries) {
      const option = RECORDING_CATEGORIES.find((c) => c.value === entry.value)!;
      expect(option).toBeDefined();
      if (entry.kind === 'cost') {
        expect(option.costCategory).toBe(entry.value);
        expect(option.expenseCategory).toBeUndefined();
      } else {
        expect(option.expenseCategory).toBe(entry.value);
        expect(option.costCategory).toBeUndefined();
      }
    }
  });

  it('keeps a UI label for every entry', () => {
    for (const option of RECORDING_CATEGORIES) {
      expect(option.label.trim().length).toBeGreaterThan(0);
    }
  });
});
