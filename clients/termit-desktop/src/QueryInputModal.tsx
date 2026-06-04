interface QueryInputModalProps {
  open: boolean;
  title: string;
  placeholder: string;
  value: string;
  submitLabel: string;
  onClose: () => void;
  onChange: (value: string) => void;
  onSubmit: () => void;
}

export function QueryInputModal({
  open,
  title,
  placeholder,
  value,
  submitLabel,
  onClose,
  onChange,
  onSubmit,
}: QueryInputModalProps) {
  if (!open) {
    return null;
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div className="modal" role="dialog" onClick={(event) => event.stopPropagation()}>
        <h3>{title}</h3>
        <textarea
          autoFocus
          rows={3}
          placeholder={placeholder}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
              event.preventDefault();
              onSubmit();
            }
          }}
        />
        <div className="row">
          <button type="button" className="secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="primary" disabled={!value.trim()} onClick={onSubmit}>
            {submitLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
