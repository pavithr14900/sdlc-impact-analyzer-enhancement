import { useState, type ReactNode } from "react";
import { ChevronRight } from "lucide-react";

interface SubsectionAccordionProps {
  icon: ReactNode;
  title: string;
  defaultOpen?: boolean;
  children: ReactNode;
}

// Shared collapsible wrapper reused across the Architecture, API Design,
// Data Model, Test Strategy and Infrastructure sections so every
// sub-block can be individually collapsed/expanded.
export default function SubsectionAccordion({
  icon,
  title,
  defaultOpen = true,
  children,
}: SubsectionAccordionProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="arch-subsection">
      <button
        type="button"
        className="arch-subsection-header arch-subsection-toggle"
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
      >
        {icon}
        <span>{title}</span>
        <ChevronRight className={`arch-subsection-chevron ${open ? "expanded" : ""}`} />
      </button>

      {open && <div className="arch-subsection-body">{children}</div>}
    </div>
  );
}
