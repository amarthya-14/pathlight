"use client";

import { useState } from "react";
import { Check } from "lucide-react";
import { Button, cx, TextInput } from "./ui";

export function Chip({ selected, onClick, children }: { selected: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={cx(
        "inline-flex h-8 items-center gap-1.5 rounded-full border px-3 text-[13px] font-medium transition-[background-color,border-color,color,transform] duration-200 active:scale-[0.97]",
        selected
          ? "border-ink bg-ink text-ink-fg"
          : "border-line-strong bg-surface text-muted hover:border-subtle hover:text-fg"
      )}
    >
      {selected && <Check size={13} strokeWidth={2.6} />}
      {children}
    </button>
  );
}

export function ChipPicker({
  options,
  value,
  onChange,
  placeholder,
  max = 6,
}: {
  options: string[];
  value: string[];
  onChange: (v: string[]) => void;
  placeholder: string;
  max?: number;
}) {
  const [custom, setCustom] = useState("");
  const all = [...options, ...value.filter((v) => !options.includes(v))];
  const toggle = (item: string) =>
    onChange(value.includes(item) ? value.filter((v) => v !== item) : value.length >= max ? value : [...value, item]);
  const addCustom = () => {
    const item = custom.trim();
    if (item && !value.includes(item) && value.length < max) onChange([...value, item]);
    setCustom("");
  };
  return (
    <div>
      <div className="flex flex-wrap gap-2">
        {all.map((item) => (
          <Chip key={item} selected={value.includes(item)} onClick={() => toggle(item)}>
            {item}
          </Chip>
        ))}
      </div>
      <div className="mt-3 flex gap-2">
        <TextInput
          value={custom}
          onChange={(e) => setCustom(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              addCustom();
            }
          }}
          placeholder={placeholder}
          className="max-w-xs"
        />
        <Button type="button" variant="secondary" onClick={addCustom} disabled={!custom.trim()}>
          Add
        </Button>
      </div>
    </div>
  );
}

