import { useEffect } from "react";

/** Global Ctrl+K / Cmd+K listener that opens the command palette from
 *  anywhere in the authenticated app, including while focus is inside a
 *  form field — mirrors GitHub/Linear/Raycast, where the shortcut always
 *  wins over whatever's focused. */
export function useCommandPaletteShortcut(onOpen: () => void) {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const isModifierK = (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k";
      if (!isModifierK) return;
      event.preventDefault();
      onOpen();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onOpen]);
}
