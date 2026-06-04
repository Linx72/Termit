import { useEffect, useState } from "react";

interface PromptInputModalProps {
  open: boolean;
  title: string;
  placeholder?: string;
  submitLabel?: string;
  initialValue?: string;
  onClose: () => void;
  onSubmit: (value: string) => void;
}

export function PromptInputModal({
  open,
  title,
  placeholder,
  submitLabel = "Apply",
  initialValue = "",
  onClose,
  onSubmit,
}: PromptInputModalProps) {
  const [value, setValue] = useState(initialValue);

  useEffect(() => {
    if (open) {
      setValue(initialValue);
    }
  }, [open, initialValue]);

  if (!open) {
    return null;
  }

  return (
    <div className="modal-backdrop prompt-input-backdrop" role="presentation" onClick={onClose}>
      <div className="modal prompt-input-modal" role="dialog" onClick={(event) => event.stopPropagation()}>
        <h3>{title}</h3>
        <input
          autoFocus
          value={value}
          placeholder={placeholder}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              const trimmed = value.trim();
              if (!trimmed) {
                return;
              }
              onSubmit(trimmed);
              onClose();
            }
          }}
        />
        <div className="row">
          <button type="button" className="secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="primary"
            disabled={!value.trim()}
            onClick={() => {
              const trimmed = value.trim();
              if (!trimmed) {
                return;
              }
              onSubmit(trimmed);
              onClose();
            }}
          >
            {submitLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
