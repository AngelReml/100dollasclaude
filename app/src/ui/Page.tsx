import type { ReactNode } from "react";

/** Screen header: title, one line of help, and the screen's main action on the right. */
export function Page({ title, subtitle, action, children }: { title: string; subtitle?: ReactNode; action?: ReactNode; children: ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-[1320px] px-5 pb-16 pt-8 md:px-10">
      <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[30px] font-bold leading-tight tracking-tight">{title}</h1>
          {subtitle && <p className="mt-1 text-[17px] text-ink-2">{subtitle}</p>}
        </div>
        {action}
      </header>
      {children}
    </div>
  );
}

export function SectionTitle({ children, className = "mb-3" }: { children: ReactNode; className?: string }) {
  return <h2 className={`${className} text-[19px] font-semibold`}>{children}</h2>;
}
