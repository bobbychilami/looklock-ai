import { useEffect, useMemo, useRef } from 'react'

export interface FilePickerProps {
  label: string
  hint: string
  file: File | null
  disabled?: boolean
  onChange: (file: File | null) => void
}

/**
 * Single-image picker with a local preview.
 *
 * The preview uses an object URL, so it never touches the network and never
 * involves the backend. The `File` itself is only sent when the form is
 * submitted.
 */
export function FilePicker({ label, hint, file, disabled = false, onChange }: FilePickerProps) {
  const inputRef = useRef<HTMLInputElement>(null)

  // Derived rather than stored: creating the URL in an effect and pushing it
  // into state would cause a second render for something already computable.
  const previewUrl = useMemo(() => (file ? URL.createObjectURL(file) : null), [file])

  useEffect(() => {
    if (!previewUrl) return
    return () => URL.revokeObjectURL(previewUrl)
  }, [previewUrl])

  return (
    <div className="flex flex-col gap-2">
      <span className="text-xs font-medium tracking-wide text-ink-500 uppercase">{label}</span>

      <div className="flex items-center gap-4">
        <div className="flex size-24 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-dashed border-ink-300 bg-ink-100/60">
          {previewUrl ? (
            <img src={previewUrl} alt={`${label} preview`} className="size-full object-cover" />
          ) : (
            <span className="px-2 text-center text-[10px] text-ink-500">no image</span>
          )}
        </div>

        <div className="flex flex-col gap-2">
          <input
            ref={inputRef}
            type="file"
            accept="image/jpeg,image/png"
            disabled={disabled}
            className="block w-full text-xs text-ink-700 file:mr-3 file:rounded-lg file:border-0 file:bg-ink-100 file:px-3 file:py-2 file:text-xs file:font-medium file:text-ink-700 hover:file:bg-ink-300/60 disabled:cursor-not-allowed"
            onChange={(event) => {
              onChange(event.target.files?.[0] ?? null)
              // Allow re-selecting the same file after a failed run.
              event.target.value = ''
            }}
          />
          {file ? (
            <button
              type="button"
              disabled={disabled}
              className="self-start text-xs text-ink-500 underline underline-offset-2 hover:text-ink-900 disabled:cursor-not-allowed"
              onClick={() => onChange(null)}
            >
              Clear
            </button>
          ) : (
            <p className="text-xs text-ink-500">{hint}</p>
          )}
        </div>
      </div>

      {file && <p className="text-xs text-ink-500">{file.name}</p>}
    </div>
  )
}