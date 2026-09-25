"use client";

import { useEffect, useRef, useState } from "react";
import { Input } from "@/components/ui/input";

interface SearchInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  minChars?: number;
  debounceMs?: number;
  className?: string;
}

export function SearchInput({
  value,
  onChange,
  placeholder,
  minChars = 3,
  debounceMs = 300,
  className,
}: SearchInputProps) {
  const [localValue, setLocalValue] = useState(value);
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  // What this box last sent up. A `value` change that is only that echo coming
  // back must not overwrite what the user is typing — a text below `minChars`
  // is sent as "" and the box has to keep showing it.
  const emittedRef = useRef(value);

  useEffect(() => {
    if (value !== emittedRef.current) {
      emittedRef.current = value;
      setLocalValue(value);
    }
  }, [value]);

  function handleChange(newValue: string) {
    setLocalValue(newValue);
    clearTimeout(timerRef.current);

    timerRef.current = setTimeout(() => {
      // Too short to search drops the filter rather than keeping the previous
      // query's results under text that no longer asks for them.
      const next = newValue.trim().length >= minChars ? newValue : "";
      if (next === emittedRef.current) return;
      emittedRef.current = next;
      onChange(next);
    }, debounceMs);
  }

  useEffect(() => {
    return () => clearTimeout(timerRef.current);
  }, []);

  return (
    <Input
      value={localValue}
      onChange={(e) => handleChange(e.target.value)}
      placeholder={placeholder}
      className={className}
    />
  );
}
