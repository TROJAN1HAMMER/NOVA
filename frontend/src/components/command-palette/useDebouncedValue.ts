import { useEffect, useState } from "react";

/** Debounces a fast-changing value (keystrokes) so expensive downstream work
 *  (Fuse search + a full result re-render) runs at most every `delayMs`. */
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(timer);
  }, [value, delayMs]);

  return debounced;
}
