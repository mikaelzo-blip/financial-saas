import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, beforeEach } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import { AuthProvider } from '../../src/store/AuthContext';
import { LoginPage } from '../../src/pages/auth/LoginPage';

describe('LoginFlow Integration', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('renders login page with credentials and quick-login buttons', () => {
    render(
      <BrowserRouter>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </BrowserRouter>
    );

    expect(screen.getByText('Financial SaaS')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('nama@kontraktor.co.id')).toBeInTheDocument();
    expect(screen.getByText('Operator')).toBeInTheDocument();
    expect(screen.getByText('Manajer')).toBeInTheDocument();
  });

  it('populates operator email when Operator quick login is clicked', () => {
    render(
      <BrowserRouter>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </BrowserRouter>
    );

    const operatorBtn = screen.getByText('Operator');
    fireEvent.click(operatorBtn);

    const emailInput = screen.getByPlaceholderText('nama@kontraktor.co.id') as HTMLInputElement;
    expect(emailInput.value).toBe('operator@kontraktor.co.id');
  });
});
