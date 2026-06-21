/* In-app browser guard: Messenger/Facebook/Instagram/etc. webviews usually aren't signed
   into Google, so the closed-test opt-in + Play install silently fail. Detect those webviews
   and surface a prominent "Open in Chrome" banner (Android: force Chrome via an intent URL;
   everyone: a copy-link fallback). No auto-redirect (avoids loops). */
(function () {
  var ua = navigator.userAgent || '';
  var apps = [
    ['Messenger', /Messenger|FBAN|FBAV|FB_IAB/i],
    ['Instagram', /Instagram/i],
    ['Facebook', /FBAN|FBAV|FB_IAB/i],
    ['Line', /Line\//i],
    ['WeChat', /MicroMessenger/i],
    ['X', /Twitter/i],
    ['Snapchat', /Snapchat/i],
    ['TikTok', /TikTok|musical_ly|BytedanceWebview/i]
  ];
  var name = null;
  for (var i = 0; i < apps.length; i++) { if (apps[i][1].test(ua)) { name = apps[i][0]; break; } }
  var isAndroid = /Android/i.test(ua);
  var androidWV = isAndroid && /;\s*wv\)/i.test(ua);
  if (!name && !androidWV) return;
  var label = name || 'this in-app';
  var url = location.href;

  function el(tag, css, html) { var e = document.createElement(tag); if (css) e.style.cssText = css; if (html != null) e.innerHTML = html; return e; }

  var bar = el('div', 'position:sticky;top:0;z-index:99999;background:#1F5C3D;color:#F4EDDF;padding:14px 16px;text-align:center;font:600 15px/1.45 -apple-system,Segoe UI,Roboto,sans-serif;box-shadow:0 2px 14px rgba(0,0,0,.28)');
  bar.setAttribute('role', 'alert');
  bar.appendChild(el('div', 'max-width:560px;margin:0 auto',
    '<b>Open this page in Chrome to join.</b><br>' +
    '<span style="font-weight:400;opacity:.92">Google sign-in won’t work inside the ' + label + ' browser — tap the <b>⋮</b> menu (top-right) and choose <b>Open in Chrome</b>.</span>'));
  var btns = el('div', 'margin-top:11px');
  var openBtn = el('button', 'background:#F4B04A;color:#2B2218;border:0;border-radius:999px;padding:10px 18px;font:700 14px sans-serif;margin:0 6px 6px 0;cursor:pointer', 'Open in Chrome');
  var copyBtn = el('button', 'background:transparent;color:#F4EDDF;border:1px solid rgba(244,237,223,.5);border-radius:999px;padding:10px 18px;font:600 14px sans-serif;cursor:pointer', 'Copy link');
  btns.appendChild(openBtn); btns.appendChild(copyBtn);
  bar.querySelector('div').appendChild(btns);

  function copy() { try { navigator.clipboard.writeText(url); return true; } catch (e) { return false; } }
  openBtn.onclick = function () {
    if (isAndroid) {
      var u = url.replace(/^https?:\/\//, '');
      window.location.href = 'intent://' + u + '#Intent;scheme=https;package=com.android.chrome;S.browser_fallback_url=' + encodeURIComponent(url) + ';end';
    } else {
      openBtn.textContent = copy() ? 'Link copied — paste in Safari' : 'Tap & hold the address bar to copy';
    }
  };
  copyBtn.onclick = function () { copyBtn.textContent = copy() ? 'Copied!' : 'Select the URL above to copy'; };

  function mount() { if (document.body) document.body.insertBefore(bar, document.body.firstChild); }
  if (document.body) mount(); else document.addEventListener('DOMContentLoaded', mount);
})();
