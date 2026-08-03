import { Moon, Sun } from "lucide-react";
import { useTheme } from "../../hooks/useTheme";
import { Button } from "../ui/Button";

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  return (
    <Button
      variant="ghost"
      size="sm"
      className="h-9 w-9 p-0"
      onClick={toggleTheme}
      aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
    >
      {theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
    </Button>
  );
}
