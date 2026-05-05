import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react';
import ConfirmModal from './ConfirmModal.jsx';
import ToastStack from './ToastStack.jsx';

// Single context exposing confirm() + toast helpers. Mounted once at the
// admin shell root so any descendant can call useConfirm() / useToast()
// without prop drilling.
const UIContext = createContext(null);

export function useUI() {
  const ctx = useContext(UIContext);
  if (!ctx) {
    throw new Error('useUI / useConfirm / useToast must be used inside <UIProvider>');
  }
  return ctx;
}

export default function UIProvider({ children }) {
  const [confirmState, setConfirmState] = useState(null); // { ...opts, resolve }
  const [toasts, setToasts] = useState([]); // [{ id, kind, message }]
  const idRef = useRef(1);

  const confirm = useCallback((opts) => {
    return new Promise((resolve) => {
      setConfirmState({
        title: '请确认',
        message: '',
        confirmLabel: '确定',
        cancelLabel: '取消',
        destructive: false,
        ...opts,
        resolve,
      });
    });
  }, []);

  const closeConfirm = useCallback((decision) => {
    setConfirmState((s) => {
      if (s) s.resolve(decision);
      return null;
    });
  }, []);

  const dismissToast = useCallback((id) => {
    setToasts((list) => list.filter((t) => t.id !== id));
  }, []);

  const pushToast = useCallback(
    (kind, message, { ttl = 3500 } = {}) => {
      const id = idRef.current++;
      setToasts((list) => [...list, { id, kind, message }]);
      if (ttl > 0) setTimeout(() => dismissToast(id), ttl);
      return id;
    },
    [dismissToast],
  );

  const toast = useMemo(
    () => ({
      success: (m, opts) => pushToast('success', m, opts),
      error: (m, opts) => pushToast('error', m, { ttl: 6000, ...(opts || {}) }),
      info: (m, opts) => pushToast('info', m, opts),
      dismiss: dismissToast,
    }),
    [pushToast, dismissToast],
  );

  const value = useMemo(() => ({ confirm, toast }), [confirm, toast]);

  return (
    <UIContext.Provider value={value}>
      {children}
      <ConfirmModal
        state={confirmState}
        onConfirm={() => closeConfirm(true)}
        onCancel={() => closeConfirm(false)}
      />
      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </UIContext.Provider>
  );
}

export function useConfirm() {
  return useUI().confirm;
}

export function useToast() {
  return useUI().toast;
}
