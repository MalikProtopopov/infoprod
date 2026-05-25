'use client';

import { ReactNode } from 'react';

import { Button, Sheet } from '@/components/ui';

/**
 * Подтверждение деструктивных действий — заменяет нативный confirm().
 *
 * Использование:
 *   const [askDelete, setAskDelete] = useState(false);
 *   <ConfirmDialog
 *     open={askDelete}
 *     onClose={() => setAskDelete(false)}
 *     onConfirm={remove}
 *     title="Удалить квиз?"
 *     description="История прохождений сохранится."
 *     confirmText="Удалить"
 *   />
 */
export function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title,
  description,
  confirmText = 'Подтвердить',
  cancelText = 'Отмена',
  destructive = true,
  busy = false,
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void | Promise<void>;
  title: string;
  description?: ReactNode;
  confirmText?: string;
  cancelText?: string;
  destructive?: boolean;
  busy?: boolean;
}) {
  return (
    <Sheet
      open={open}
      onClose={onClose}
      title={title}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            {cancelText}
          </Button>
          <Button
            variant={destructive ? 'danger' : 'primary'}
            onClick={onConfirm}
            disabled={busy}
          >
            {busy ? 'Подождите…' : confirmText}
          </Button>
        </>
      }
    >
      {description && (
        <div className="text-sm text-zinc-700 leading-relaxed">{description}</div>
      )}
    </Sheet>
  );
}
