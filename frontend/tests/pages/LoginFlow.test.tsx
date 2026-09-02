import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import { AuthProvider } from '../../src/store/AuthContext';
import { LoginPage } from '../../src/pages/auth/LoginPage';
import { authApi } from '../../src/api/auth';

describe('LoginFlow Integration', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });


  it('renders empty credential fields without hardcoded demo accounts', () => {
    render(
      <BrowserRouter>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </BrowserRouter>
    );

    expect(screen.getByText('Financial SaaS')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('nama@kontraktor.co.id')).toHaveValue('');
    expect(screen.getByPlaceholderText('••••••••')).toHaveValue('');
    expect(screen.queryByText('Pilihan Akun Demo (Satu Klik)')).not.toBeInTheDocument();
  });

  it('shows a useful message for rejected credentials', async () => {
    vi.spyOn(authApi, 'login').mockRejectedValue(new Error('Email atau kata sandi tidak valid.'));
    render(
      <BrowserRouter>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </BrowserRouter>
    );

    fireEvent.change(screen.getByPlaceholderText('nama@kontraktor.co.id'), {
      target: { value: 'invalid@example.test' },
    });
    fireEvent.change(screen.getByPlaceholderText('••••••••'), {
      target: { value: 'invalid-password' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Masuk ke Aplikasi' }));

    expect(await screen.findByText('Email atau kata sandi tidak valid.')).toBeInTheDocument();
  });
});
