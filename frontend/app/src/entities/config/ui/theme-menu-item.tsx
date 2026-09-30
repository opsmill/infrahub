import { Menu, MenuItem, Popover, SubmenuTrigger } from "@infrahub/ui";
import { MonitorIcon, MoonIcon, SunIcon, SunMoonIcon } from "lucide-react";
import { type Selection, Text } from "react-aria-components";

import { Badge } from "@/shared/components/ui/badge";

import { type Theme, ThemeSchema } from "@/entities/config/domain/model/theme";
import { useFeatureFlag } from "@/entities/config/ui/hooks/use-feature-flag";
import { useTheme } from "@/entities/config/ui/theme-provider";

const LABELS: Record<Theme, string> = {
  system: "System",
  light: "Light",
  dark: "Dark",
};

export function ThemeMenuItem() {
  const isDarkThemeEnabled = useFeatureFlag("dark_theme");
  const { theme, setTheme } = useTheme();

  if (!isDarkThemeEnabled) {
    return null;
  }

  const handleSelectionChange = (keys: Selection) => {
    const [next] = keys === "all" ? [] : keys;
    const parsedTheme = ThemeSchema.safeParse(next);
    if (parsedTheme.success) {
      setTheme(parsedTheme.data);
    }
  };

  return (
    <SubmenuTrigger>
      <MenuItem textValue="Theme">
        <SunMoonIcon />
        <Text slot="label" className="flex-1">
          Theme
        </Text>
        <Text slot="description" className="text-subtle-muted">
          {LABELS[theme]}
        </Text>
      </MenuItem>

      <Popover>
        <Menu
          aria-label="Theme"
          selectionMode="single"
          disallowEmptySelection
          selectedKeys={[theme]}
          onSelectionChange={handleSelectionChange}
        >
          <MenuItem id="system" textValue={LABELS.system}>
            <MonitorIcon />
            {LABELS.system}
          </MenuItem>
          <MenuItem id="light" textValue={LABELS.light}>
            <SunIcon />
            {LABELS.light}
          </MenuItem>
          <MenuItem id="dark" textValue={LABELS.dark}>
            <MoonIcon />
            <Text slot="label">{LABELS.dark}</Text>
            <Text slot="description">
              <Badge variant="yellow">alpha</Badge>
            </Text>
          </MenuItem>
        </Menu>
      </Popover>
    </SubmenuTrigger>
  );
}
