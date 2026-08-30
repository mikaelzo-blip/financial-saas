import { describe, it, expect } from 'vitest';
import { validateAllocationSum } from '../../src/utils/transactionValidation';

describe('validateAllocationSum', () => {
  it('returns valid when allocations sum exactly matches total nominal', () => {
    const allocations = [
      { project_id: 'p1', amount: 5000000 },
      { project_id: 'p2', amount: 3000000 },
      { project_id: 'p3', amount: 2000000 },
    ];
    const res = validateAllocationSum(10000000, allocations);
    expect(res.isValid).toBe(true);
    expect(res.difference).toBe(0);
  });

  it('returns invalid when allocations sum does not match total nominal', () => {
    const allocations = [
      { project_id: 'p1', amount: 5000000 },
      { project_id: 'p2', amount: 4000000 },
    ];
    const res = validateAllocationSum(10000000, allocations);
    expect(res.isValid).toBe(false);
    expect(res.difference).toBe(1000000);
    expect(res.errorMessage).toBeDefined();
  });

  it('handles string amounts with formatting gracefully', () => {
    const allocations = [
      { project_id: 'p1', amount: '2500000.50' },
      { project_id: 'p2', amount: '7499999.50' },
    ];
    const res = validateAllocationSum('10000000', allocations);
    expect(res.isValid).toBe(true);
    expect(res.allocationSum).toBe(10000000);
  });
});
