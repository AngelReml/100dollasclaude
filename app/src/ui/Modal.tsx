import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { ReactNode } from "react";

export function Modal({
  open,
  onOpenChange,
  title,
  description,
  children,
  wide = false,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: ReactNode;
  wide?: boolean;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40" />
        <Dialog.Content
          onOpenAutoFocus={(e) => {
            e.preventDefault();
            (e.currentTarget as HTMLElement).focus();
          }}
          tabIndex={-1}
          className={
            "focus:outline-none " +
            "animate-pop fixed left-1/2 top-1/2 z-40 max-h-[calc(100vh-48px)] w-[calc(100vw-32px)] -translate-x-1/2 -translate-y-1/2 " +
            "overflow-y-auto rounded-2xl border border-line bg-surface p-6 shadow-pop " +
            (wide ? "max-w-3xl" : "max-w-xl")
          }
        >
          <div className="mb-4 flex items-start gap-4">
            <div className="flex-1">
              <Dialog.Title className="text-[21px] font-semibold leading-tight">{title}</Dialog.Title>
              {description ? (
                <Dialog.Description className="mt-1 text-ink-2">{description}</Dialog.Description>
              ) : (
                <Dialog.Description className="sr-only">{title}</Dialog.Description>
              )}
            </div>
            <Dialog.Close className="cursor-pointer rounded-lg p-1.5 text-muted hover:bg-surface-2 hover:text-ink" aria-label="Cerrar">
              <X size={20} />
            </Dialog.Close>
          </div>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
