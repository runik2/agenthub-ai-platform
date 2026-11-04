import { useI18n, type Lang } from "../i18n";
import { cn } from "../lib/utils";

const options: { value: Lang; label: string }[] = [
  { value: "ru", label: "RU" },
  { value: "en", label: "EN" },
];

export function LanguageToggle({ className }: { className?: string }) {
  const { lang, setLang, t } = useI18n();
  return (
    <div
      role="group"
      aria-label={t("topbar.language")}
      className={cn("inline-flex rounded-lg border border-line bg-card p-0.5", className)}
    >
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => setLang(option.value)}
          aria-pressed={lang === option.value}
          className={cn(
            "rounded-md px-2 py-1 text-[11px] font-semibold tracking-wide transition-colors",
            lang === option.value ? "bg-raised text-ink" : "text-muted hover:text-ink",
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
