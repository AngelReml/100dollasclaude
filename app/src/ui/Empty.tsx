import type { ReactNode } from "react";

/** An empty screen that teaches: what goes here, an example, a button. */
export function Empty({ icon, title, text, children }: { icon: ReactNode; title: string; text: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed border-line-strong bg-surface/60 px-6 py-10 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-accent-soft text-accent-soft-ink">{icon}</div>
      <h2 className="text-[19px] font-semibold">{title}</h2>
      <p className="max-w-xl text-ink-2">{text}</p>
      {children && <div className="mt-2 flex w-full flex-col items-center gap-2">{children}</div>}
    </div>
  );
}
