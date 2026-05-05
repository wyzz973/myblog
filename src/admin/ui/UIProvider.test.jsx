import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup, act } from '@testing-library/react';
import UIProvider, { useConfirm, useToast } from './UIProvider.jsx';

afterEach(() => cleanup());

function ConfirmHarness({ onResult, opts }) {
  const confirm = useConfirm();
  return (
    <button
      type="button"
      onClick={async () => {
        const r = await confirm(opts || {});
        onResult(r);
      }}
    >
      ask
    </button>
  );
}

function ToastHarness({ kind, message }) {
  const toast = useToast();
  return (
    <button type="button" onClick={() => toast[kind](message)}>
      ping
    </button>
  );
}

describe('useConfirm', () => {
  it('resolves true when the user clicks 确定', async () => {
    const onResult = vi.fn();
    render(
      <UIProvider>
        <ConfirmHarness onResult={onResult} opts={{ title: '删除', message: '不可撤销' }} />
      </UIProvider>,
    );
    fireEvent.click(screen.getByText('ask'));
    expect(await screen.findByTestId('confirm-modal')).toBeTruthy();
    expect(screen.getByText('不可撤销')).toBeTruthy();
    fireEvent.click(screen.getByTestId('confirm-ok'));
    await new Promise((r) => setTimeout(r, 0));
    expect(onResult).toHaveBeenCalledWith(true);
    expect(screen.queryByTestId('confirm-modal')).toBeNull();
  });

  it('resolves false on 取消', async () => {
    const onResult = vi.fn();
    render(
      <UIProvider>
        <ConfirmHarness onResult={onResult} />
      </UIProvider>,
    );
    fireEvent.click(screen.getByText('ask'));
    await screen.findByTestId('confirm-modal');
    fireEvent.click(screen.getByTestId('confirm-cancel'));
    await new Promise((r) => setTimeout(r, 0));
    expect(onResult).toHaveBeenCalledWith(false);
  });

  it('Escape resolves false', async () => {
    const onResult = vi.fn();
    render(
      <UIProvider>
        <ConfirmHarness onResult={onResult} />
      </UIProvider>,
    );
    fireEvent.click(screen.getByText('ask'));
    await screen.findByTestId('confirm-modal');
    fireEvent.keyDown(document, { key: 'Escape' });
    await new Promise((r) => setTimeout(r, 0));
    expect(onResult).toHaveBeenCalledWith(false);
  });

  it('uses the provided destructive style cue via testid', async () => {
    render(
      <UIProvider>
        <ConfirmHarness onResult={() => {}} opts={{ destructive: true, confirmLabel: '删除' }} />
      </UIProvider>,
    );
    fireEvent.click(screen.getByText('ask'));
    const ok = await screen.findByTestId('confirm-ok');
    expect(ok.textContent).toBe('删除');
  });
});

describe('useToast', () => {
  it('renders a success toast', () => {
    render(
      <UIProvider>
        <ToastHarness kind="success" message="保存成功" />
      </UIProvider>,
    );
    fireEvent.click(screen.getByText('ping'));
    expect(screen.getByTestId('toast-success')).toBeTruthy();
    expect(screen.getByText('保存成功')).toBeTruthy();
  });

  it('renders an error toast with longer ttl', () => {
    render(
      <UIProvider>
        <ToastHarness kind="error" message="出错了" />
      </UIProvider>,
    );
    fireEvent.click(screen.getByText('ping'));
    expect(screen.getByTestId('toast-error')).toBeTruthy();
  });

  it('clicking a toast dismisses it', () => {
    render(
      <UIProvider>
        <ToastHarness kind="info" message="hi" />
      </UIProvider>,
    );
    fireEvent.click(screen.getByText('ping'));
    const t = screen.getByTestId('toast-info');
    fireEvent.click(t);
    expect(screen.queryByTestId('toast-info')).toBeNull();
  });

  it('auto-dismisses after ttl', async () => {
    vi.useFakeTimers();
    try {
      render(
        <UIProvider>
          <ToastHarness kind="success" message="x" />
        </UIProvider>,
      );
      fireEvent.click(screen.getByText('ping'));
      expect(screen.getByTestId('toast-success')).toBeTruthy();
      act(() => {
        vi.advanceTimersByTime(4000);
      });
      expect(screen.queryByTestId('toast-success')).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it('throws helpful error if used outside provider', () => {
    function Bare() {
      useToast();
      return null;
    }
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => render(<Bare />)).toThrow(/inside <UIProvider>/);
    spy.mockRestore();
  });
});
