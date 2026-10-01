/* Alibi components: window.Alibi.
   React 18 through window.React (no JSX, no imports). Styled only by bundle.css (class prefix al-), which carries the token block.
   Pinch is drawn by window.AlibiPinch (pinch.js, concatenated before this file); without it Alibi.Pinch shows a still green disc. */
(function () {
  'use strict';

  /* ---------- helpers ---------- */
  function R() { return window.React; }
  function h() { var React = R(); return React.createElement.apply(React, arguments); }
  function cx() {
    var out = [];
    for (var i = 0; i < arguments.length; i++) if (arguments[i]) out.push(arguments[i]);
    return out.join(' ');
  }
  function rest(props, used) {
    var o = {};
    for (var k in props) if (Object.prototype.hasOwnProperty.call(props, k) && used.indexOf(k) < 0) o[k] = props[k];
    return o;
  }
  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
  function pct(v) { return Math.round(clamp(Number(v) || 0, 0, 1) * 100); }
  function reducedMotion() {
    try { return window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) { return false; }
  }
  function safeId(id) { return 'al' + String(id).replace(/[^A-Za-z0-9_-]/g, ''); }

  /* ---------- Icon: 1.5px stroke on a 24 grid, round caps and joins, currentColor ---------- */
  var ICONS = {
    play: [['path', { d: 'M8 5.6v12.8a1 1 0 0 0 1.53.85l10.2-6.4a1 1 0 0 0 0-1.7L9.53 4.75A1 1 0 0 0 8 5.6z' }]],
    pause: [['rect', { x: 6.5, y: 5, width: 3.5, height: 14, rx: 1 }], ['rect', { x: 14, y: 5, width: 3.5, height: 14, rx: 1 }]],
    stop: [['rect', { x: 6, y: 6, width: 12, height: 12, rx: 2.5 }]],
    plus: [['path', { d: 'M12 5v14M5 12h14' }]],
    check: [['path', { d: 'M5 12.5l4.5 4.5L19 7.5' }]],
    x: [['path', { d: 'M6.5 6.5l11 11M17.5 6.5l-11 11' }]],
    camera: [['path', { d: 'M4 8.5A1.5 1.5 0 0 1 5.5 7h2.4l1.3-2h5.6l1.3 2h2.4A1.5 1.5 0 0 1 20 8.5v9a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 17.5z' }], ['circle', { cx: 12, cy: 12.75, r: 3.25 }]],
    laptop: [['rect', { x: 5, y: 5.5, width: 14, height: 10, rx: 1.5 }], ['path', { d: 'M3 18.5h18' }]],
    phone: [['rect', { x: 7, y: 3, width: 10, height: 18, rx: 2.5 }], ['path', { d: 'M11 18h2' }]],
    run: [['circle', { cx: 15.5, cy: 4.5, r: 1.75 }], ['path', { d: 'M13.5 7.5L10.5 13M13.2 8.4l2.8 1.8 2.5-.6M12.9 8.2l-3 .3-2.2 2M10.5 13l3.4 2-.6 4.5M10.5 13l-1.3 3.4H5.5' }]],
    heart: [['path', { d: 'M12 19.5s-7.5-4.4-7.5-10A4.25 4.25 0 0 1 12 6.9a4.25 4.25 0 0 1 7.5 2.6c0 5.6-7.5 10-7.5 10z' }]],
    moon: [['path', { d: 'M19.5 14.6A7.75 7.75 0 1 1 9.4 4.5a6.25 6.25 0 0 0 10.1 10.1z' }]],
    calendar: [['rect', { x: 4, y: 5.5, width: 16, height: 14.5, rx: 2.5 }], ['path', { d: 'M4 10h16M8.5 3.5v4M15.5 3.5v4' }]],
    settings: [['path', { d: 'M10.07 5.27L10.72 2.89L13.28 2.89L13.93 5.27A7 7 0 0 1 15.39 5.88L17.54 4.65L19.35 6.46L18.12 8.61A7 7 0 0 1 18.73 10.07L21.11 10.72L21.11 13.28L18.73 13.93A7 7 0 0 1 18.12 15.39L19.35 17.54L17.54 19.35L15.39 18.12A7 7 0 0 1 13.93 18.73L13.28 21.11L10.72 21.11L10.07 18.73A7 7 0 0 1 8.61 18.12L6.46 19.35L4.65 17.54L5.88 15.39A7 7 0 0 1 5.27 13.93L2.89 13.28L2.89 10.72L5.27 10.07A7 7 0 0 1 5.88 8.61L4.65 6.46L6.46 4.65L8.61 5.88A7 7 0 0 1 10.07 5.27Z' }], ['circle', { cx: 12, cy: 12, r: 3 }]],
    lens: [['circle', { cx: 10.5, cy: 10.5, r: 6 }], ['path', { d: 'M15 15l5 5' }]],
    cup: [['path', { d: 'M5 9.5h11v4A5.5 5.5 0 0 1 10.5 19h0A5.5 5.5 0 0 1 5 13.5z' }], ['path', { d: 'M16 11h1.25a2.5 2.5 0 0 1 0 5H15.4M8.5 3.5v3M12.5 3.5v3' }]],
    'arrow-up': [['path', { d: 'M12 19V5M6 11l6-6 6 6' }]],
    'arrow-right': [['path', { d: 'M5 12h14M13 6l6 6-6 6' }]],
    'chevron-right': [['path', { d: 'M9.5 6l6 6-6 6' }]],
    'chevron-down': [['path', { d: 'M6 9.5l6 6 6-6' }]],
    clock: [['circle', { cx: 12, cy: 12, r: 8.5 }], ['path', { d: 'M12 7.5V12l3 2' }]],
    flag: [['path', { d: 'M5.5 21V4.5M5.5 4.5h11.5l-2.25 4 2.25 4H5.5' }]],
    eye: [['path', { d: 'M2.75 12S6.25 5.75 12 5.75 21.25 12 21.25 12 17.75 18.25 12 18.25 2.75 12 2.75 12z' }], ['circle', { cx: 12, cy: 12, r: 3 }]],
    sparkle: [['path', { d: 'M12 3.5c.75 4.75 2.75 7.25 7.5 8.5-4.75 1.25-6.75 3.75-7.5 8.5-.75-4.75-2.75-7.25-7.5-8.5 4.75-1.25 6.75-3.75 7.5-8.5z' }]],
    claw: [['path', { d: 'M7.5 20.5C4.8 17.8 4.6 13.2 6.9 9.6 8.6 7 11.1 4.9 14.2 3.5c.2 2.6-.4 5.1-1.7 7.2 2.5-1 5.4-1.1 8.3-.3-1.3 3.5-4.4 5.9-8 6.5-1.4.3-2.4 1.6-2.7 3.6z' }], ['path', { d: 'M7.5 20.5h2.6' }]],
    undo: [['path', { d: 'M9 13.5L4 8.5l5-5' }], ['path', { d: 'M4 8.5h10.25a5.75 5.75 0 0 1 0 11.5H10' }]],
    film: [['rect', { x: 4, y: 4, width: 16, height: 16, rx: 2.5 }], ['path', { d: 'M8.5 4v16M15.5 4v16M4 9h4.5M4 15h4.5M15.5 9H20M15.5 15H20' }]]
  };

  function Icon(p) {
    var size = p.size || 20;
    var parts = ICONS[p.name];
    if (!parts) return null;
    var attrs = {
      className: cx('al-icon', p.className),
      width: size, height: size, viewBox: '0 0 24 24',
      fill: 'none', stroke: 'currentColor', strokeWidth: 1.5, strokeLinecap: 'round', strokeLinejoin: 'round',
      focusable: 'false'
    };
    if (p.title) { attrs.role = 'img'; attrs['aria-label'] = p.title; } else { attrs['aria-hidden'] = 'true'; }
    return h('svg', attrs, parts.map(function (part, i) { return h(part[0], Object.assign({ key: i }, part[1])); }));
  }
  Icon.names = Object.keys(ICONS);

  /* ---------- Digit roll: each digit is a 0-9 reel moved by translateY on spring-snappy ---------- */
  var DIGITS = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'];
  function Roll(p) {
    var text = String(p.value == null ? '' : p.value);
    var chars = text.split('');
    var n = chars.length;
    return h('span', { className: 'al-roll' },
      h('span', { className: 'al-sr' }, text),
      h('span', { className: 'al-roll__vis', 'aria-hidden': 'true' }, chars.map(function (c, i) {
        var key = n - i;   // keyed from the right, so the units digit keeps its reel when the length changes
        if (c >= '0' && c <= '9') {
          return h('span', { key: 'd' + key, className: 'al-roll__col' },
            h('span', { className: 'al-roll__reel', style: { transform: 'translateY(' + (-Number(c)) + 'em)' } },
              DIGITS.map(function (d) { return h('span', { key: d }, d); })));
        }
        return h('span', { key: 's' + key + c, className: 'al-roll__sym' }, c);
      })));
  }

  /* ---------- Kbd ---------- */
  function Kbd(p) {
    return h('kbd', Object.assign(rest(p, ['children', 'className']), { className: cx('al-kbd', p.className) }), p.children);
  }

  /* ---------- Button ---------- */
  var ICON_PX = { sm: 16, md: 16, lg: 20 };
  function Button(p) {
    var variant = p.variant || 'secondary';
    var size = p.size || 'md';
    var iconOnly = !!p.iconOnly;
    var label = p.ariaLabel || (iconOnly && typeof p.children === 'string' ? p.children : undefined);
    var attrs = Object.assign({ type: 'button' },
      rest(p, ['variant', 'size', 'icon', 'iconOnly', 'ariaLabel', 'children', 'className']), {
        className: cx('al-btn', 'al-btn--' + variant, 'al-btn--' + size, iconOnly && 'al-btn--icon', p.className),
        'aria-label': label
      });
    return h('button', attrs,
      p.icon ? h(Icon, { name: p.icon, size: ICON_PX[size] || 16 }) : null,
      iconOnly ? null : (p.children != null ? h('span', { className: 'al-btn__label' }, p.children) : null));
  }

  function IconButton(p) {
    var size = p.size || 'md';
    var attrs = Object.assign({ type: 'button' }, rest(p, ['icon', 'ariaLabel', 'size', 'className']), {
      className: cx('al-iconbtn', 'al-iconbtn--' + size, p.className),
      'aria-label': p.ariaLabel
    });
    return h('button', attrs, h(Icon, { name: p.icon, size: size === 'lg' ? 24 : (size === 'sm' ? 16 : 20) }));
  }

  /* ---------- Chip ---------- */
  function Chip(p) {
    var selected = !!p.selected;
    var attrs = Object.assign({ type: 'button' }, rest(p, ['selected', 'icon', 'kbd', 'children', 'className']), {
      className: cx('al-chip', selected && 'is-selected', p.className),
      'aria-pressed': selected
    });
    return h('button', attrs,
      p.icon ? h(Icon, { name: p.icon, size: 16 }) : null,
      h('span', { className: 'al-chip__label' }, p.children),
      p.kbd ? h(Kbd, null, p.kbd) : null);
  }

  /* ---------- Composer ---------- */
  var composerStack = [];   // the first mounted composer answers "/"
  function Composer(p) {
    var React = R();
    var placeholder = p.placeholder || 'What are you about to do?';
    var controlled = typeof p.onChange === 'function' && p.value != null;
    var st = React.useState(p.value || '');
    var text = controlled ? p.value : st[0];
    var setText = function (v) { if (!controlled) st[1](v); if (p.onChange) p.onChange(v); };
    var fs = React.useState(false);
    var focused = !!p.focused || fs[0];
    var inputRef = React.useRef(null);
    var chips = p.chips || [];

    React.useEffect(function () {
      var me = { focus: function () { if (inputRef.current) inputRef.current.focus(); } };
      composerStack.push(me);
      function onKey(e) {
        if (e.key !== '/' || composerStack[0] !== me || e.metaKey || e.ctrlKey || e.altKey) return;
        var t = e.target, tag = t && t.tagName;
        if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || (t && t.isContentEditable)) return;
        e.preventDefault(); me.focus();
      }
      document.addEventListener('keydown', onKey);
      return function () {
        document.removeEventListener('keydown', onKey);
        var i = composerStack.indexOf(me); if (i >= 0) composerStack.splice(i, 1);
      };
    }, []);

    function submit() {
      var v = String(text || '').trim();
      if (!v) return;
      if (p.onSubmit) p.onSubmit(v);
    }
    function pick(i) {
      if (!chips[i]) return;
      setText(chips[i]);
      if (inputRef.current) inputRef.current.focus();
    }
    function onKeyDown(e) {
      if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); submit(); }
      else if (e.key === 'Escape') { e.currentTarget.blur(); }
      else if ((e.metaKey || e.ctrlKey) && /^[1-9]$/.test(e.key)) { e.preventDefault(); pick(Number(e.key) - 1); }
    }
    var has = String(text || '').trim().length > 0;
    return h('div', { className: cx('al-composer', focused && 'is-focused', has && 'has-text', p.className) },
      h('div', { className: 'al-composer__field' },
        h('input', {
          ref: inputRef, className: 'al-composer__input', type: 'text', value: text,
          placeholder: placeholder, 'aria-label': placeholder, autoComplete: 'off', spellCheck: false,
          enterKeyHint: 'go',
          onChange: function (e) { setText(e.target.value); },
          onFocus: function () { fs[1](true); },
          onBlur: function () { fs[1](false); },
          onKeyDown: onKeyDown
        }),
        (!has && !focused) ? h(Kbd, { className: 'al-composer__hint', title: 'Press / to type' }, '/') : null,
        h('button', {
          type: 'button', className: 'al-composer__send', 'aria-label': 'Start session',
          disabled: !has, onClick: submit
        }, h(Icon, { name: 'arrow-up', size: 20 }))),
      chips.length ? h('div', { className: 'al-composer__chips', role: 'group', 'aria-label': 'Habits' },
        chips.map(function (c, i) {
          return h(Chip, {
            key: c + i, kbd: i < 9 ? '⌘' + (i + 1) : null,
            selected: String(text).trim() === c,
            onClick: function () { pick(i); }
          }, c);
        })) : null);
  }

  /* ---------- Card ---------- */
  function Card(p) {
    var tag = p.as || 'div';
    var attrs = Object.assign(rest(p, ['as', 'tone', 'padding', 'children', 'className']), {
      className: cx('al-card', 'al-card--' + (p.tone || 'default'), 'al-card--pad-' + (p.padding || 'md'), p.className)
    });
    return h(tag, attrs, p.children);
  }

  /* ---------- StatusDot: colour plus shape, always ---------- */
  var STATUS = {
    on_task: { word: 'On task', cls: 'on-task' },
    idle: { word: 'Idle', cls: 'idle' },
    phone: { word: 'Phone', cls: 'phone' },
    off_task: { word: 'Off task', cls: 'off-task' },
    absent: { word: 'Away', cls: 'absent' }
  };
  function DotMark(label, s, clipId) {
    var c = s / 2, r = s * 0.4;
    if (label === 'on_task') return [h('circle', { key: 'a', cx: c, cy: c, r: r, fill: 'currentColor' })];
    if (label === 'idle') return [h('circle', { key: 'a', cx: c, cy: c, r: r - 1, fill: 'none', stroke: 'currentColor', strokeWidth: 2 })];
    if (label === 'phone') {
      var side = s * 0.76, o = (s - side) / 2;
      return [h('rect', { key: 'a', x: o, y: o, width: side, height: side, rx: s * 0.2, fill: 'currentColor' })];
    }
    if (label === 'off_task') {
      var step = Math.max(2.5, s / 4.5), lines = [];
      for (var k = -s; k <= s; k += step) lines.push('M' + k + ' ' + s + 'L' + (k + s) + ' 0');
      return [
        h('clipPath', { key: 'c', id: clipId }, h('circle', { cx: c, cy: c, r: r })),
        h('circle', { key: 'f', cx: c, cy: c, r: r, fill: 'currentColor', opacity: 0.28 }),
        h('path', { key: 'h', d: lines.join(''), stroke: 'currentColor', strokeWidth: Math.max(1, s / 10), clipPath: 'url(#' + clipId + ')' }),
        h('circle', { key: 'o', cx: c, cy: c, r: r - 0.6, fill: 'none', stroke: 'currentColor', strokeWidth: 1.2 })
      ];
    }
    var rr = r - 0.75, circ = 2 * Math.PI * rr, dash = circ / Math.max(6, Math.round(s / 1.6));
    return [h('circle', { key: 'a', cx: c, cy: c, r: rr, fill: 'none', stroke: 'currentColor', strokeWidth: 1.5, strokeDasharray: (dash * 0.55) + ' ' + (dash * 0.45) })];
  }
  function StatusDot(p) {
    var React = R();
    var uid = React.useId ? React.useId() : 'x';
    var label = STATUS[p.label] ? p.label : 'absent';
    var s = p.size || 12;
    var info = STATUS[label];
    var svg = h('svg', {
      className: 'al-dot__mark', width: s, height: s, viewBox: '0 0 ' + s + ' ' + s, 'aria-hidden': 'true', focusable: 'false'
    }, DotMark(label, s, safeId(uid) + 'h'));
    var attrs = Object.assign(rest(p, ['label', 'size', 'text', 'className']), {
      className: cx('al-dot', 'al-dot--' + info.cls, s < 16 && 'is-small', p.className)
    });
    if (p.text) return h('span', attrs, svg, h('span', { className: 'al-dot__word' }, info.word));
    attrs.role = 'img'; attrs['aria-label'] = info.word;
    return h('span', attrs, svg);
  }

  /* ---------- SampleStrip: the last samples, newest on the right ---------- */
  function SampleStrip(p) {
    var labels = p.labels || [];
    var size = p.size || 28;
    var frames = p.frames || null;
    var last = labels.length - 1;
    var words = labels.map(function (l) { return (STATUS[l] || STATUS.absent).word.toLowerCase(); });
    return h('div', {
      className: cx('al-strip', p.develop && 'is-develop', frames && 'has-frames', p.className),
      role: 'img', 'aria-label': 'Last ' + labels.length + ' samples: ' + words.join(', ')
    }, labels.map(function (l, i) {
      var newest = i === last;
      var key = newest && p.develop ? 'new-' + labels.length + '-' + labels.join('.') : 'c' + (last - i);
      var img = frames && frames[i] ? h('img', { className: 'al-strip__img', src: frames[i], alt: '' }) : null;
      return h('span', {
        key: key, className: cx('al-strip__cell', newest && p.develop && 'is-new'),
        style: frames ? { width: Math.round(size * 16 / 9), height: size } : { width: size, height: size }
      },
        img,
        h('span', { className: 'al-strip__dot' }, h(StatusDot, { label: l, size: Math.max(8, Math.round(size * (frames ? 0.36 : 0.43))) })));
    }));
  }

  /* ---------- VerdictPill: glyph and word, always ---------- */
  var VERDICT = {
    done: { word: 'Done', aria: 'done' },
    partial: { word: 'Partly', aria: 'partly' },
    slacked: { word: 'Slacked', aria: 'slacked' }
  };
  function VerdictGlyph(v) {
    var common = { width: 14, height: 14, viewBox: '0 0 16 16', 'aria-hidden': 'true', focusable: 'false', className: 'al-verdict__glyph' };
    if (v === 'done') return h('svg', common, h('path', { d: 'M3.5 8.4l3 3 6-6.4', fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' }));
    if (v === 'partial') return h('svg', common,
      h('circle', { cx: 8, cy: 8, r: 5.5, fill: 'none', stroke: 'currentColor', strokeWidth: 1.75 }),
      h('path', { d: 'M8 2.5a5.5 5.5 0 0 1 0 11z', fill: 'currentColor' }));
    return h('svg', common, h('path', { d: 'M4.5 4.5l7 7M11.5 4.5l-7 7', fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round' }));
  }
  function VerdictPill(p) {
    var v = VERDICT[p.verdict] ? p.verdict : 'partial';
    var hasRatio = p.ratio != null && !isNaN(p.ratio);
    var r = hasRatio ? pct(p.ratio) : null;
    var attrs = Object.assign(rest(p, ['verdict', 'ratio', 'className']), {
      className: cx('al-verdict', 'al-verdict--' + v, p.className), role: 'img',
      'aria-label': 'Verdict: ' + VERDICT[v].aria + (hasRatio ? ', ' + r + '%' : '')
    });
    return h('span', attrs, VerdictGlyph(v),
      h('span', { className: 'al-verdict__word' }, VERDICT[v].word),
      hasRatio ? h('span', { className: 'al-verdict__ratio' }, r + '%') : null);
  }

  /* ---------- Meter: scaleX fill with ticks at partAt and doneAt ---------- */
  function useSettle(ms) {
    // false on the first frame, then true: lets a fill animate in from zero, then retarget on a different curve
    var React = R();
    var s = React.useState(0);
    React.useEffect(function () {
      var raf2, t;
      var raf1 = requestAnimationFrame(function () {
        raf2 = requestAnimationFrame(function () { s[1](1); t = setTimeout(function () { s[1](2); }, ms); });
      });
      return function () { cancelAnimationFrame(raf1); cancelAnimationFrame(raf2); clearTimeout(t); };
    }, []);
    return s[0];
  }
  function Meter(p) {
    var v = clamp(Number(p.value) || 0, 0, 1);
    var partAt = p.partAt == null ? 0.4 : p.partAt;
    var doneAt = p.doneAt == null ? 0.7 : p.doneAt;
    var tone = v >= doneAt ? 'done' : (v >= partAt ? 'partial' : 'slacked');
    var phase = useSettle(900);
    var shown = phase === 0 && !reducedMotion() ? 0 : v;
    var attrs = Object.assign(rest(p, ['value', 'partAt', 'doneAt', 'className', 'label']), {
      className: cx('al-meter', 'al-meter--' + tone, phase === 2 && 'is-settled', p.className),
      role: 'meter', 'aria-valuemin': 0, 'aria-valuemax': 100, 'aria-valuenow': pct(v),
      'aria-label': p.label || ('On task ' + pct(v) + '%')
    });
    return h('div', attrs,
      h('div', { className: 'al-meter__track' },
        h('div', { className: 'al-meter__fill', style: { transform: 'scaleX(' + shown + ')' } })),
      h('span', { className: 'al-meter__tick', style: { left: (partAt * 100) + '%' }, 'aria-hidden': 'true' }),
      h('span', { className: 'al-meter__tick', style: { left: (doneAt * 100) + '%' }, 'aria-hidden': 'true' }));
  }

  /* ---------- RingTimer ---------- */
  function RingTimer(p) {
    var size = p.size || 160;
    var tone = p.tone || 'accent';
    var prog = clamp(Number(p.progress) || 0, 0, 1);
    var stroke = Math.max(3, Math.round(size / 16));
    var rad = (size - stroke) / 2;
    var circ = 2 * Math.PI * rad;
    var phase = useSettle(700);
    var shown = phase === 0 && !reducedMotion() ? 0 : prog;
    var compact = size < 88;
    var attrs = Object.assign(rest(p, ['progress', 'value', 'caption', 'size', 'tone', 'className']), {
      className: cx('al-ring', 'al-ring--' + tone, phase === 2 && 'is-ticking', compact && 'is-compact', p.className),
      style: { width: size, height: size },
      role: 'progressbar', 'aria-valuemin': 0, 'aria-valuemax': 100, 'aria-valuenow': pct(prog),
      'aria-valuetext': [p.value, p.caption, pct(prog) + '% elapsed'].filter(Boolean).join(', ')
    });
    return h('div', attrs,
      h('svg', { className: 'al-ring__svg', width: size, height: size, viewBox: '0 0 ' + size + ' ' + size, 'aria-hidden': 'true', focusable: 'false' },
        h('circle', { className: 'al-ring__track', cx: size / 2, cy: size / 2, r: rad, strokeWidth: stroke, fill: 'none' }),
        h('circle', {
          className: 'al-ring__arc', cx: size / 2, cy: size / 2, r: rad, strokeWidth: stroke, fill: 'none',
          strokeLinecap: 'round', strokeDasharray: circ, strokeDashoffset: circ * (1 - shown),
          style: { opacity: shown > 0.002 ? 1 : 0 }
        })),
      compact ? null : h('div', { className: 'al-ring__center', 'aria-hidden': 'true' },
        h('span', { className: 'al-ring__value', style: { fontSize: Math.round(size * 0.24) } }, p.value),
        p.caption ? h('span', { className: 'al-ring__caption' }, p.caption) : null));
  }

  /* ---------- Stat ---------- */
  function Stat(p) {
    var attrs = Object.assign(rest(p, ['value', 'label', 'sub', 'className']), { className: cx('al-stat', p.className) });
    return h('div', attrs,
      h('span', { className: 'al-stat__label' }, p.label),
      h('span', { className: 'al-stat__value' }, h(Roll, { value: p.value })),
      p.sub ? h('span', { className: 'al-stat__sub' }, p.sub) : null);
  }

  /* ---------- StreakBadge: claw glyph plus a rolling digit, never a flame ---------- */
  function StreakBadge(p) {
    var React = R();
    var days = Math.max(0, Math.round(Number(p.days) || 0));
    var bump = React.useState(false);
    var prev = React.useRef(days);
    React.useEffect(function () {
      if (days > prev.current && !reducedMotion()) {
        bump[1](true);
        var t = setTimeout(function () { bump[1](false); }, 140);
        prev.current = days;
        return function () { clearTimeout(t); };
      }
      prev.current = days;
    }, [days]);
    var fr = p.freezes;
    var freezeText = fr > 0 ? (fr + (fr === 1 ? ' freeze left' : ' freezes left')) : null;
    var dayWord = days === 1 ? ' day' : ' days';
    var attrs = Object.assign(rest(p, ['days', 'freezes', 'className']), {
      className: cx('al-streak', bump[0] && 'is-bumping', p.className), role: 'img',
      'aria-label': 'Streak: ' + days + dayWord + (freezeText ? ', ' + freezeText : '')
    });
    return h('span', attrs,
      h(Icon, { name: 'claw', size: 16 }),
      h('span', { className: 'al-streak__days', 'aria-hidden': 'true' }, h(Roll, { value: days }), dayWord),
      freezeText ? h('span', { className: 'al-streak__freeze', 'aria-hidden': 'true' }, freezeText) : null);
  }

  /* ---------- Pinch: wraps the AlibiPinch engine ---------- */
  function Pinch(p) {
    var React = R();
    var size = p.size || 96;
    var mood = p.mood || 'idle';
    var host = React.useRef(null);
    var inst = React.useRef(null);
    var engine = window.AlibiPinch;
    var still = !!p.still || reducedMotion();
    var theme = p.theme || 'auto';

    React.useEffect(function () {
      if (!engine || !host.current) return undefined;
      var i = engine.mount(host.current, { size: size, mood: mood, theme: theme, still: still });
      inst.current = i;
      return function () { try { i.destroy(); } catch (e) { /* already gone */ } inst.current = null; };
    }, [engine, theme, still]);
    React.useEffect(function () { if (inst.current) inst.current.set(mood); }, [mood]);
    React.useEffect(function () { if (inst.current) inst.current.setSize(size); }, [size]);
    React.useEffect(function () {
      if (!p.play || !inst.current) return;
      var r = inst.current.play(p.play, { force: !!p.force });
      if (r && typeof r.catch === 'function') r.catch(function () { /* dropped by the cooldown */ });
    }, [p.play, p.playKey]);

    var style = { width: size, height: size };
    if (!engine) {
      return h('span', { className: cx('al-pinch', 'is-placeholder', p.className), style: style, 'aria-hidden': 'true' },
        h('span', { className: 'al-pinch__disc' }));
    }
    return h('span', { ref: host, className: cx('al-pinch', p.className), style: style, 'aria-hidden': 'true', 'data-mood': mood });
  }

  /* ---------- PinchLine: a 20px Pinch and one line in Alibi's voice ---------- */
  function PinchLine(p) {
    var attrs = Object.assign(rest(p, ['mood', 'children', 'compact', 'className', 'theme']), {
      className: cx('al-pinchline', p.compact && 'is-compact', p.className)
    });
    return h('div', attrs,
      h('span', { className: 'al-pinchline__avatar' }, h(Pinch, { mood: p.mood || 'idle', size: 20, theme: p.theme })),
      h('p', { className: 'al-pinchline__text' }, p.children));
  }

  /* ---------- Toast ---------- */
  function renderAction(a, i) {
    if (a == null) return null;
    if (R().isValidElement(a)) return R().cloneElement(a, { key: a.key != null ? a.key : i });
    return h(Button, { key: a.label + i, variant: a.variant || (i === 0 ? 'primary' : 'quiet'), size: 'sm', onClick: a.onClick, icon: a.icon }, a.label);
  }
  function Toast(p) {
    var kind = p.kind || 'info';
    var attrs = Object.assign(rest(p, ['kind', 'title', 'children', 'actions', 'onClose', 'icon', 'mood', 'className']), {
      className: cx('al-toast', 'al-toast--' + kind, p.className), role: 'status', 'aria-live': 'polite'
    });
    var body = kind === 'info'
      ? h('div', { className: 'al-toast__info' },
          p.icon ? h('span', { className: 'al-toast__icon' }, h(Icon, { name: p.icon, size: 20 })) : null,
          h('p', { className: 'al-toast__text' }, p.children))
      : h(PinchLine, { mood: p.mood || (kind === 'nudge' ? 'focused' : 'idle') }, p.children);
    return h('div', attrs,
      h('div', { className: 'al-toast__head' },
        h('span', { className: 'al-toast__title' }, p.title),
        p.onClose ? h(IconButton, { icon: 'x', size: 'sm', ariaLabel: 'Dismiss', onClick: p.onClose, className: 'al-toast__close' }) : null),
      body,
      p.actions && p.actions.length ? h('div', { className: 'al-toast__actions' }, p.actions.map(renderAction)) : null);
  }

  /* ---------- NotchIsland: one black shape whose clip animates; notch 185 x 32 ---------- */
  var NOTCH_W = 185;
  var ISLAND = {
    idle: { w: 185, band: 32, r: 10, f: 6 },
    live: { w: 277, band: 32, r: 12, f: 6, wings: true },
    peek: { w: 289, band: 36, r: 14, f: 6, wings: true },
    'break': { w: 277, band: 32, r: 12, f: 6, wings: true },
    expanded: { w: 400, band: 32, r: 28, f: 12, panel: true, min: 180 },
    nudge: { w: 400, band: 32, r: 28, f: 12, panel: true, min: 140 },
    verdict: { w: 440, band: 32, r: 28, f: 12, panel: true, min: 180 }
  };
  var ISLAND_MAX_H = 400;
  function islandCurve(from, to) {
    var a = ISLAND[from], b = ISLAND[to];
    if (a.panel && !b.panel) return 'smooth';
    if (b.panel && !a.panel) return (to === 'expanded') ? 'island' : 'bouncy';
    if (b.panel && a.panel) return (to === 'expanded') ? 'smooth' : 'bouncy';
    return 'snappy';
  }
  function Flare(side) {
    var d = side === 'l' ? 'M0 0H12V12A12 12 0 0 0 0 0Z' : 'M12 0H0V12A12 12 0 0 1 12 0Z';
    return h('svg', { className: 'al-island__flare al-island__flare--' + side, width: 12, height: 12, viewBox: '0 0 12 12', 'aria-hidden': 'true', focusable: 'false' },
      h('path', { d: d }));
  }
  function NotchIsland(p) {
    var React = R();
    var target = ISLAND[p.state] ? p.state : 'idle';
    var visS = React.useState(target);
    var vis = visS[0];
    var leavingS = React.useState(false);
    var leaving = leavingS[0];
    var curve = React.useRef('snappy');
    var lastBody = React.useRef(null);
    var contentRef = React.useRef(null);
    var measuredS = React.useState(0);
    var shakeS = React.useState(false);

    React.useEffect(function () {
      if (target === vis) return undefined;
      if (ISLAND[vis].panel && !ISLAND[target].panel && !reducedMotion()) {
        leavingS[1](true);                      // content leaves first (100ms), then the shape folds
        var t = setTimeout(function () {
          curve.current = 'smooth';
          leavingS[1](false);
          visS[1](target);
        }, 100);
        return function () { clearTimeout(t); };
      }
      curve.current = islandCurve(vis, target);
      leavingS[1](false);
      visS[1](target);
      return undefined;
    }, [target]);

    React.useEffect(function () {
      if (vis !== 'nudge' || !p.shake || reducedMotion()) return undefined;
      shakeS[1](true);
      var t = setTimeout(function () { shakeS[1](false); }, 1100);
      return function () { clearTimeout(t); };
    }, [vis, p.shake]);

    var spec = ISLAND[vis];
    if (spec.panel && !leaving) lastBody.current = p.children;
    var body = spec.panel ? (leaving ? lastBody.current : p.children) : null;

    React.useLayoutEffect(function () {
      if (!spec.panel || !contentRef.current) return undefined;
      var el = contentRef.current;
      var measure = function () { measuredS[1](el.offsetHeight); };
      measure();
      if (typeof ResizeObserver === 'undefined') return undefined;
      var ro = new ResizeObserver(measure);
      ro.observe(el);
      return function () { ro.disconnect(); };
    }, [vis, spec.panel]);

    var w = (spec.panel && p.width) ? p.width : spec.w;
    var hgt = spec.panel ? clamp(Math.max(measuredS[0], spec.min), spec.min, 360) : spec.band;
    var maxW = Math.max(440, p.width || 0);
    var c = curve.current;
    var style = {
      height: hgt,
      '--al-isl-w': w + 'px',
      '--al-isl-h': hgt + 'px',
      '--al-isl-r': spec.r + 'px',
      '--al-isl-f': String(spec.f / 12),
      '--al-isl-band': spec.band + 'px',
      '--al-isl-max': maxW + 'px',
      '--al-isl-ease': 'var(--spring-' + c + ')',
      '--al-isl-dur': 'var(--spring-' + c + '-dur)'
    };
    var zone = (w - NOTCH_W) / 2;
    var bandStyle = spec.panel ? { gridTemplateColumns: '1fr ' + NOTCH_W + 'px 1fr' } : { gridTemplateColumns: zone + 'px ' + NOTCH_W + 'px ' + zone + 'px' };
    var attrs = Object.assign(rest(p, ['state', 'width', 'leading', 'trailing', 'children', 'shake', 'className', 'label']), {
      className: cx('al-island', 'al-island--' + vis, spec.panel && 'is-panel', spec.wings && 'has-wings', leaving && 'is-leaving', shakeS[0] && 'is-shaking', p.className),
      'data-theme': 'dark', style: style,
      role: 'region', 'aria-label': p.label || 'Alibi island'
    });
    var showBand = vis !== 'idle';
    return h('div', attrs,
      h('div', { className: 'al-island__lift' },
        Flare('l'), Flare('r'),
        h('div', { className: 'al-island__shape' },
          h('div', { className: 'al-island__content', ref: contentRef },
            showBand ? h('div', { className: 'al-island__band', style: bandStyle },
              h('div', { className: 'al-island__lead' }, p.leading),
              h('div', { className: 'al-island__notch', 'aria-hidden': 'true' }),
              h('div', { className: 'al-island__trail' }, p.trailing)) : null,
            body != null ? h('div', { key: vis, className: 'al-island__body' }, body) : null))));
  }

  /* ---------- export ---------- */
  var Alibi = window.Alibi || {};
  Object.assign(Alibi, {
    Button: Button, IconButton: IconButton, Icon: Icon, Chip: Chip, Kbd: Kbd, Composer: Composer, Card: Card,
    StatusDot: StatusDot, SampleStrip: SampleStrip, VerdictPill: VerdictPill, Meter: Meter, RingTimer: RingTimer,
    Stat: Stat, StreakBadge: StreakBadge, PinchLine: PinchLine, Pinch: Pinch, NotchIsland: NotchIsland, Toast: Toast
  });
  window.Alibi = Alibi;
})();
