import { useCallback, useRef, useState } from 'react';

/**
 * Controlled/uncontrolled state. If `value` is defined the parent owns the state;
 * otherwise it lives here. `onChange` fires only when the value actually changes.
 */
export function useControllable<T>(
  value: T | undefined,
  defaultValue: T,
  onChange?: (v: T) => void,
): [T, (v: T) => void] {
  const [internal, setInternal] = useState<T>(defaultValue);
  const controlled = value !== undefined;
  const current = controlled ? (value as T) : internal;
  const currentRef = useRef(current);
  currentRef.current = current;
  const cbRef = useRef(onChange);
  cbRef.current = onChange;

  const set = useCallback(
    (next: T) => {
      if (Object.is(next, currentRef.current)) return;
      if (!controlled) setInternal(next);
      cbRef.current?.(next);
    },
    [controlled],
  );
  return [current, set];
}
