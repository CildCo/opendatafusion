(function (global) {
  "use strict";

  var script = document.currentScript;
  var base = "/ui/";
  if (script && script.src) {
    base = script.src.replace(/odf-embed\.js(?:\?.*)?$/, "");
  }

  function resolveTarget(target) {
    if (typeof target === "string") return document.querySelector(target);
    return target || null;
  }

  function url(token, params) {
    var query = "";
    if (params && typeof params === "object") {
      var pairs = [];
      Object.keys(params).forEach(function (key) {
        pairs.push(encodeURIComponent(key) + "="
          + encodeURIComponent(params[key]));
      });
      if (pairs.length) query = "?" + pairs.join("&");
    }
    return base + "#/embed/" + encodeURIComponent(token) + query;
  }

  function mount(options) {
    var opts = options || {};
    var host = resolveTarget(opts.target);
    if (!host) throw new Error("ODFEmbed: target not found");
    if (!opts.token) throw new Error("ODFEmbed: token is required");
    var frame = document.createElement("iframe");
    frame.src = url(opts.token, opts.params);
    frame.title = opts.title || "OpenDataFusion";
    frame.loading = "lazy";
    frame.style.border = "0";
    frame.style.width = opts.width || "100%";
    frame.style.height = (opts.height || 720) + "px";
    frame.style.display = "block";
    frame.setAttribute("allowfullscreen", "");
    host.appendChild(frame);

    var source = new URL(frame.src).origin;
    function onMessage(event) {
      if (event.source !== frame.contentWindow || event.origin !== source) {
        return;
      }
      var data = event.data || {};
      if (data.type === "odf-embed:resize" && data.height) {
        frame.style.height = Math.max(120, Number(data.height)) + "px";
      }
    }
    global.addEventListener("message", onMessage);
    var api = {
      element: frame,
      url: frame.src,
      unmount: function () {
        global.removeEventListener("message", onMessage);
        if (frame.parentNode) frame.parentNode.removeChild(frame);
      },
    };
    return api;
  }

  global.ODFEmbed = { mount: mount, url: url, base: base };
})(window);
