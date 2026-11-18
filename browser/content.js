function startShield() {
  const api = globalThis.browser ?? globalThis.chrome;
  const html = document.documentElement;
  const telegram = /^(web\.telegram\.org|t\.me|telegram\.me)$/.test(location.hostname);
  const message = '[data-message-id],.Message,.bubble[data-mid],.bubbles-group .bubble,.message-list-item,.tgme_widget_message_wrap,.chatlist-chat';
  const chatHeader = '#MiddleColumn .chat-info,#MiddleColumn .ChatInfo,.chat-topbar .peer-title,.chat-topbar .peer-title-inner,.tgme_channel_info_header_title';
  const posts = 'article,[role="article"],[data-testid="tweet"],shreddit-post,shreddit-comment,ytd-rich-item-renderer,ytd-video-renderer,ytd-compact-video-renderer,ytd-comment-thread-renderer';
  const blocks = 'p,li,td,blockquote,h1,h2,h3,h4,h5,h6,a,button,summary,[role="alert"],[role="listitem"]';
  const mediaText = '[title],[alt],[aria-label],[href]';
  const ignore = 'script,style,template,noscript,textarea,input,select,[contenteditable]:not([contenteditable="false"]),#spoiler-shield-screen';
  const separators = /^(BR|DIV|P|LI|TR|TD|SECTION|ARTICLE|H[1-6]|BLOCKQUOTE|HEADER|FOOTER|SUMMARY)$/;
  const coverTitle = 'Hidden by SpoilerVeil';
  const hidden = new Set();
  let enabled = true;
  let filter = globalThis.spoilerFilter.compile();
  let titleBeforeCover = null;
  let cover = null;
  let settingsReady = false;

  const sourcePage = telegram || /(^|\.)reddit\.com$/.test(location.hostname);

  function urlMatches(value) {
    try {
      return filter(decodeURIComponent(new URL(value, location.href).pathname));
    } catch {
      return false;
    }
  }

  function group(el) {
    return (telegram && el.closest(message))
      || el.closest(posts) || el.closest(blocks) || el;
  }

  function setHidden(el, value) {
    if (value && el !== document.body && el !== html) {
      hidden.add(el);
      if (!el.hasAttribute('data-shield-hidden')) el.setAttribute('data-shield-hidden', '');
    } else {
      hidden.delete(el);
      el.removeAttribute('data-shield-hidden');
    }
  }

  function protectedPage() {
    const title = document.title;
    if (title !== coverTitle) titleBeforeCover = title;
    const hitsTitle = filter(titleBeforeCover);
    const hitsChat = telegram && [...document.querySelectorAll(chatHeader)]
      .some(el => filter(el.textContent));
    const bareText = document.body && [...document.body.childNodes]
      .some(node => node.nodeType === Node.TEXT_NODE && filter(node.nodeValue));
    const wholePage = enabled && (hitsTitle || hitsChat || bareText || (sourcePage && urlMatches(location.href)));
    html.toggleAttribute('data-shield-page', wholePage);
    if (wholePage && document.body) {
      if (!cover?.isConnected) {
        cover = document.createElement('div');
        cover.id = 'spoiler-shield-screen';
        cover.setAttribute('role', 'status');
        cover.textContent = telegram
          ? 'SpoilerVeil hid this chat. Use the browser’s Back button to leave.'
          : 'SpoilerVeil hid this page. Use the browser’s Back button to leave.';
        document.body.append(cover);
      }
      if (title !== coverTitle) document.title = coverTitle;
    } else {
      cover?.remove();
      if (title === coverTitle && titleBeforeCover !== null) document.title = titleBeforeCover;
    }
  }

  function collect(el, checks) {
    if (!el?.isConnected || el.closest(ignore + ',head')) return;
    if (el !== html && el !== document.body) {
      const target = group(el);
      if (target !== el || hidden.has(el) || el.matches(mediaText + ',' + blocks + ',' + posts)
          || (telegram && el.matches(message))) checks.add(target);
    }
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        return node.nodeValue.trim() && !node.parentElement?.closest(ignore + ',head')
          ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
      },
    });
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const target = group(node.parentElement);
      if (target !== html && target !== document.body) checks.add(target);
    }
    for (const item of el.querySelectorAll(mediaText)) {
      if (!item.closest(ignore)) checks.add(group(item));
    }
  }

  function blockText(root) {
    const pieces = [];
    function append(node) {
      if (node.nodeType === Node.TEXT_NODE) {
        pieces.push(node.nodeValue);
      } else if (node.nodeType === Node.ELEMENT_NODE && !node.matches(ignore)) {
        const boundary = separators.test(node.tagName);
        if (boundary) pieces.push(' ');
        for (const child of node.childNodes) append(child);
        if (boundary) pieces.push(' ');
      }
    }
    append(root);
    return pieces.join('');
  }

  function hasTrigger(el) {
    // Preserve inline words but separate neighboring paragraphs.
    if (el.textContent.length < 50000 && filter(blockText(el))) return true;
    const attributes = ['title', 'alt', 'aria-label', 'href'];
    const candidates = [el, ...el.querySelectorAll(mediaText)];
    return candidates.some(item => attributes.some(name => {
      const value = item.getAttribute(name);
      if (!value) return false;
      if (name !== 'href') return filter(value);
      return urlMatches(value);
    }));
  }

  function scan(roots) {
    if (enabled) {
      const checks = new Set();
      for (const el of roots) collect(el, checks);
      for (const el of checks) setHidden(el, hasTrigger(el));
      for (const el of hidden) if (!el.isConnected) setHidden(el, false);
    }
    protectedPage();
    if (settingsReady && document.body && document.readyState !== 'loading') {
      html.setAttribute('data-shield-ready', '');
    }
  }

  const observer = new MutationObserver(records => {
    const roots = new Set();
    for (const change of records) {
      const target = change.target.nodeType === Node.ELEMENT_NODE
        ? change.target : change.target.parentElement;
      if (target && target !== html && target !== document.body) roots.add(target);
      for (const child of change.addedNodes) {
        if (child.nodeType === Node.ELEMENT_NODE) roots.add(child);
      }
    }
    // Avoid rescanning subtrees when their parent is already in the batch.
    scan([...roots].filter(el => {
      for (let p = el.parentElement; p; p = p.parentElement) if (roots.has(p)) return false;
      return true;
    }));
  });

  function configure(settings) {
    enabled = settings.enabled !== false;
    filter = globalThis.spoilerFilter.compile(settings.extra ?? '', settings.related !== false);
    html.toggleAttribute('data-shield-enabled', enabled);
    html.toggleAttribute('data-shield-telegram-media', enabled && telegram && settings.media !== false);
    if (!enabled) for (const el of hidden) setHidden(el, false);
    settingsReady = true;
    scan([document.body]);
  }

  html.setAttribute('data-shield-enabled', '');
  if (telegram) html.setAttribute('data-shield-telegram-media', '');
  observer.observe(document, {
    subtree: true, childList: true, characterData: true, attributes: true,
    attributeFilter: ['title','alt','href','aria-label','data-message-id','data-mid'],
  });
  document.addEventListener('DOMContentLoaded', () => scan([document.body]), {once:true});
  api.storage.local.get(['enabled','extra','related','media']).then(configure, () => configure({}));
  api.storage.onChanged.addListener((_, area) => {
    if (area === 'local') api.storage.local.get(['enabled','extra','related','media']).then(configure).catch(() => {});
  });
}

if (document.documentElement) startShield();
else {
  const waitForRoot = new MutationObserver(() => {
    if (!document.documentElement) return;
    waitForRoot.disconnect();
    startShield();
  });
  waitForRoot.observe(document, {childList:true});
}
