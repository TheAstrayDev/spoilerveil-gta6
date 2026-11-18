(() => {
  const lookalikes = Object.fromEntries(
    Array.from('авекмнорстухіг', (letter, i) => [letter, 'abekmhopctyxig'[i]])
  );
  const normalize = (text) => String(text ?? '').normalize('NFKD').toLowerCase()
    .replace(/[\p{M}\p{Cf}]/gu, '')
    .replace(/[авекмнорстухіг]/g, letter => lookalikes[letter])
    .replace(/[^\p{L}\p{N}]+/gu, ' ').trim();
  const escape = text => text.replace(/[.*+?^{}()|[\]\\$]/g, '\\$&');

  function compile(extra = '', related = true) {
    const defaults = globalThis.shieldDefaults;
    const compact = defaults.aliases.map(alias =>
      Array.from(normalize(alias).replaceAll(' ', ''), escape).join(' *')
    );
    const extraTerms = extra.split(/\r?\n/)
      .map(line => normalize(line.slice(0, 240)))
      .filter(line => line.length >= 2 && line.length <= 150);
    const terms = [...new Set(extraTerms)].slice(0, 250);
    if (related) terms.push(...defaults.terms.map(normalize));
    const patterns = [...compact, ...terms.map(escape)].sort((a, b) => b.length - a.length);
    const filter = new RegExp('(?:^| )(?:' + patterns.join('|') + ')(?=$| )', 'u');
    return text => filter.test(normalize(text));
  }

  globalThis.spoilerFilter = {compile};
})();
