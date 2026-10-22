(function (root) {
  'use strict';
  const rows = typeof module !== 'undefined' && module.exports ? require('./translations.js') : root.FamilyH1Translations;
  const LOCALES = Object.freeze(['zh-CN', 'en-US']);
  const fail = () => { throw new Error('Presentation unavailable'); };
  function parameters(text) {
    const names = [...text.matchAll(/\{([a-zA-Z]+)\}/g)].map(m => m[1]).sort();
    if (/[{}]/.test(text.replace(/\{[a-zA-Z]+\}/g, ''))) fail();
    return names;
  }
  function compile(entries) {
    const dictionaries = Object.fromEntries(LOCALES.map(l => [l, Object.create(null)]));
    for (const entry of entries) {
      if (!Array.isArray(entry) || entry.length !== 3) fail();
      const [key, en, zh] = entry;
      if (typeof key !== 'string' || !/^[A-Za-z0-9 .:_&+-]{1,120}$/.test(key) || Object.hasOwn(dictionaries['en-US'], key)) fail();
      if ([en, zh].some(s => typeof s !== 'string' || !s || s.length > 1000) || JSON.stringify(parameters(en)) !== JSON.stringify(parameters(zh))) fail();
      dictionaries['en-US'][key] = en; dictionaries['zh-CN'][key] = zh;
    }
    return Object.freeze(Object.fromEntries(LOCALES.map(l => [l, Object.freeze(dictionaries[l])])));
  }
  const dictionaries = compile(rows);
  function t(locale, key, values = {}) {
    if (!LOCALES.includes(locale) || !Object.hasOwn(dictionaries[locale], key)) fail();
    const text = dictionaries[locale][key];
    const names = [...new Set(parameters(text))].sort();
    if (!values || JSON.stringify(Object.keys(values).sort()) !== JSON.stringify(names)) fail();
    for (const value of Object.values(values)) if (!['number', 'string'].includes(typeof value) || (typeof value === 'number' && !Number.isFinite(value)) || String(value).length > 1000) fail();
    // Returns plain text; callers must use textContent, never HTML parsing.
    return text.replace(/\{([a-zA-Z]+)\}/g, (_, name) => String(values[name]));
  }
  function number(locale, value) { if (!LOCALES.includes(locale) || !Number.isFinite(value)) fail(); return new Intl.NumberFormat(locale).format(value); }
  function date(locale, value, full = false) {
    if (!value) return t(locale, 'format.unknownDate');
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) fail();
    return new Intl.DateTimeFormat(locale, {...(full ? {year: 'numeric', weekday: 'long', month: 'long', day: 'numeric'} : {month: 'short', day: 'numeric'}), timeZone: 'UTC'}).format(new Date(`${value}T12:00:00Z`));
  }
  function month(locale, value) { return new Intl.DateTimeFormat(locale, {month: 'short', timeZone: 'UTC'}).format(new Date(`${value}T12:00:00Z`)); }
  function time(locale, value) {
    if (!value) return t(locale, 'format.unknownTime');
    if (!/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(value)) fail();
    return new Intl.DateTimeFormat(locale, {hour: 'numeric', minute: '2-digit', hour12: locale === 'en-US', timeZone: 'UTC'}).format(new Date(`2031-04-14T${value}:00Z`));
  }
  class Preferences {
    constructor() { this.reset(); }
    reset() { this.languages = {nora: 'zh-CN', julian: 'zh-CN'}; }
    get(member) { if (typeof member !== 'string' || !Object.hasOwn(this.languages, member)) fail(); return this.languages[member]; }
    set(member, locale) { this.get(member); if (!LOCALES.includes(locale)) fail(); this.languages[member] = locale; }
  }
  const api = {LOCALES, dictionaries, compile, parameters, t, number, date, month, time, Preferences};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.FamilyH1I18n = api;
})(globalThis);
