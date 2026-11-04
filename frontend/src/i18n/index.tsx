import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { en } from "./en";
import { ru, type Dict } from "./ru";

export type Lang = "ru" | "en";

const dictionaries: Record<Lang, Dict> = { ru, en };
const STORAGE_KEY = "agenthub.lang";

export type DictPath = string;

function lookup(dict: Dict, path: string): string | undefined {
  const parts = path.split(".");
  let current: unknown = dict;
  for (const part of parts) {
    if (typeof current !== "object" || current === null || !(part in current)) {
      return undefined;
    }
    current = (current as Record<string, unknown>)[part];
  }
  return typeof current === "string" ? current : undefined;
}

function interpolate(template: string, params?: Record<string, string | number>): string {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (match, key: string) =>
    key in params ? String(params[key]) : match,
  );
}

interface I18nValue {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: (path: DictPath, params?: Record<string, string | number>) => string;
  formatDate: (value: string | null | undefined, withTime?: boolean) => string;
  formatNumber: (value: number) => string;
}

const I18nContext = createContext<I18nValue | null>(null);

function readLang(): Lang {
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return stored === "en" || stored === "ru" ? stored : "ru";
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(readLang);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = useCallback((next: Lang) => {
    window.localStorage.setItem(STORAGE_KEY, next);
    setLangState(next);
  }, []);

  const value = useMemo<I18nValue>(() => {
    const locale = lang === "ru" ? "ru-RU" : "en-US";
    const dict = dictionaries[lang];
    return {
      lang,
      setLang,
      t: (path, params) => {
        const raw = lookup(dict, path) ?? lookup(dictionaries.ru, path);
        if (raw === undefined) {
          return path;
        }
        return interpolate(raw, params);
      },
      formatDate: (input, withTime = false) => {
        if (!input) return "—";
        const date = new Date(input);
        if (Number.isNaN(date.getTime())) return "—";
        return date.toLocaleString(locale, {
          day: "2-digit",
          month: "short",
          year: "numeric",
          ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
        });
      },
      formatNumber: (input) => new Intl.NumberFormat(locale).format(input),
    };
  }, [lang, setLang]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error("useI18n must be used inside I18nProvider");
  }
  return context;
}
