import { AxiosError } from 'axios';
import { expect, it } from 'vitest';
import { parseApiError } from '../../src/api/errorHandler';

it('shows the backend application error message', () => {
  const error = new AxiosError(
    'Request failed',
    'ERR_BAD_REQUEST',
    undefined,
    undefined,
    {
      status: 404,
      statusText: 'Not Found',
      headers: {},
      config: {} as never,
      data: {
        success: false,
        error: { code: 'NOT_FOUND', message: 'Customer tidak ditemukan.', details: {} },
      },
    },
  );

  expect(parseApiError(error).message).toBe('Customer tidak ditemukan.');
});

it('shows FastAPI field validation details', () => {
  const error = new AxiosError(
    'Request failed',
    'ERR_BAD_REQUEST',
    undefined,
    undefined,
    {
      status: 422,
      statusText: 'Unprocessable Entity',
      headers: {},
      config: {} as never,
      data: { detail: [{ loc: ['body', 'start_date'], msg: 'Input should be a valid date' }] },
    },
  );

  expect(parseApiError(error).message).toBe('start_date: Input should be a valid date');
});
