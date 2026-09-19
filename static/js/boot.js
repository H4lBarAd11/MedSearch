// MedSearch — runs first: PDF.js worker, and the request token on every call
// to our own server. Server values arrive in window.MS (templates/index.html).

if (window.pdfjsLib) {
  pdfjsLib.GlobalWorkerOptions.workerSrc = '/static/vendor/pdfjs/pdf.worker.min.js';
}

// Every request to our own server carries this launch's token; the server
// refuses requests without it, so other web pages can't drive the app.
const MEDSEARCH_TOKEN = MS.token;
const APP_VERSION = MS.appVersion;
(function () {
  const nativeFetch = window.fetch.bind(window);
  window.fetch = (input, init) => {
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    if (url.startsWith('/')) {
      init = Object.assign({}, init);
      const headers = new Headers(init.headers || {});
      headers.set('X-MedSearch-Token', MEDSEARCH_TOKEN);
      init.headers = headers;
    }
    return nativeFetch(input, init);
  };
})();
// EventSource can't send headers, so its URLs carry the token instead.
function withToken(url) {
  return url + (url.includes('?') ? '&' : '?') + 't=' + encodeURIComponent(MEDSEARCH_TOKEN);
}
