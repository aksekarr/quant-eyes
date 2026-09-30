(function () {
  "use strict";

  // Enhancements are reversible, including failures in later event callbacks.
  var originals = [];
  var disposers = [];
  var temporary = new Set();
  var frames = new Set();
  var timers = new Set();
  var running = new Map();
  var failed = false;
  var reduced;
  var fine;
  var phone;
  var observer;
  var pending = new Map();
  var stopHeadlines = function () {};
  var motionClasses = ["qx-grow", "qx-drain", "qx-timeline", "qx-correlation", "qx-sweep", "qx-chain"];

  function all(selector, root) {
    return Array.from((root || document).querySelectorAll(selector));
  }

  function restore() {
    if (failed) return;
    failed = true;
    frames.forEach(function (id) { window.cancelAnimationFrame(id); });
    timers.forEach(function (id) { window.clearTimeout(id); });
    disposers.forEach(function (dispose) { dispose(); });
    temporary.forEach(function (node) { node.remove(); });
    originals.forEach(function (record) {
      record.attributes.forEach(function (attribute) {
        if (attribute[1] === null) record.node.removeAttribute(attribute[0]);
        else record.node.setAttribute(attribute[0], attribute[1]);
      });
    });
  }

  function guard(action) {
    return function () {
      if (failed) return;
      try { return action.apply(null, arguments); }
      catch (error) { restore(); }
    };
  }

  function listen(target, event, action, options) {
    var callback = guard(action);
    target.addEventListener(event, callback, options);
    disposers.push(function () { target.removeEventListener(event, callback, options); });
  }

  function frame(action) {
    var id = window.requestAnimationFrame(guard(function (time) {
      frames.delete(id);
      action(time);
    }));
    frames.add(id);
    return id;
  }

  function later(action, delay) {
    var id = window.setTimeout(guard(function () {
      timers.delete(id);
      action();
    }), delay);
    timers.add(id);
    return id;
  }

  function onceVisible(node, action) {
    if (!node || reduced.matches || !observer) return;
    pending.set(node, action);
    observer.observe(node);
  }

  function animate(node, name, duration) {
    if (reduced.matches || node.classList.contains(name)) return;
    node.classList.add(name);
    later(function () { node.classList.remove(name); }, duration);
  }

  function count(figure) {
    if (reduced.matches || running.has(figure)) return;
    var text = figure.textContent.trim();
    var parts = /^(−?)(£?)((?:\d{1,3}(?:,\d{3})+|\d+))(\.\d+)?(%)?$/.exec(text);
    if (!parts) return;
    var target = Number(parts[3].replace(/,/g, "") + (parts[4] || ""));
    var from = Number(figure.getAttribute("data-qx-from") || "0");
    if (!Number.isFinite(target) || !Number.isFinite(from)) return;
    var decimals = parts[4] ? parts[4].length - 1 : 0;
    var commas = parts[3].indexOf(",") !== -1;
    var digits = document.createElement("span");
    digits.classList.add("qx-count-digits");
    digits.setAttribute("aria-hidden", "true");
    temporary.add(digits);
    figure.appendChild(digits);
    figure.classList.add("qx-counting");
    var started;
    function finish() {
      figure.classList.remove("qx-counting");
      digits.remove();
      temporary.delete(digits);
      running.delete(figure);
    }
    running.set(figure, finish);
    function tick(time) {
      if (!running.has(figure)) return;
      if (started === undefined) started = time;
      var progress = Math.min((time - started) / 1200, 1);
      if (progress === 1 || reduced.matches) {
        finish();
        return;
      }
      var value = (from + (target - from) * (1 - Math.pow(1 - progress, 3))).toFixed(decimals);
      var fields = value.split(".");
      if (commas) fields[0] = fields[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
      // The only text assignment: passing digits in the disposable, silent overlay.
      digits.textContent = parts[1] + parts[2] + fields.join(".") + (parts[5] || "");
      frame(tick);
    }
    frame(tick);
  }

  function setupMotion() {
    if (typeof window.IntersectionObserver === "function") {
      observer = new window.IntersectionObserver(guard(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting && entry.intersectionRatio >= 0.5) {
            var action = pending.get(entry.target);
            pending.delete(entry.target);
            observer.unobserve(entry.target);
            if (!reduced.matches && action) action();
          }
        });
      }), { threshold: 0.5 });
      disposers.push(function () { observer.disconnect(); });
    }
    all('[data-qx="figure"]').forEach(function (figure) {
      if (!figure.hasAttribute("data-qx-from")) onceVisible(figure, function () { count(figure); });
    });
    // Observe the visual inside its card: even a card taller than the viewport works.
    all('[data-layout="bars"]').forEach(function (bars) {
      onceVisible(bars, function () {
        all('[data-layout="bar-track"]', bars).forEach(function (track) { animate(track, "qx-grow", 1250); });
      });
    });
    all('[data-layout="drain"]').forEach(function (drain) {
      onceVisible(drain, function () {
        count(drain.querySelector('[data-qx="figure"]'));
        animate(drain.querySelector('[data-layout="drain-track"]'), "qx-drain", 1250);
      });
    });
    [["timeline-track", "qx-timeline", 1250], ["correlation", "qx-correlation", 1250],
      ["mix", "qx-grow", 1250], ["chain", "qx-chain", 1500]].forEach(function (item) {
      all('[data-layout="' + item[0] + '"]').forEach(function (node) {
        onceVisible(node, function () { animate(node, item[1], item[2]); });
      });
    });
    all('[data-layout="headline"], [data-layout="headlines"]').forEach(function (node) {
      onceVisible(node, function () { animate(node, "qx-sweep", 1650); });
      listen(node, "pointerenter", function () {
        if (fine.matches) animate(node, "qx-sweep", 1650);
      });
    });
  }

  function setupSearch() {
    var search = document.querySelector('[data-layout="search"]');
    if (!search) return;
    var input = search.querySelector('input[type="search"]');
    var results = all("li", search);
    var missing = search.querySelector('[data-layout="not-covered"]');
    var labels = results.map(function (result) { return result.textContent.toLowerCase(); });
    function filter() {
      var query = input.value.trim().toLowerCase();
      var matches = 0;
      results.forEach(function (result, index) {
        result.hidden = !query || labels[index].indexOf(query) === -1;
        if (!result.hidden) matches += 1;
      });
      missing.hidden = !query || matches !== 0;
    }
    listen(input, "input", filter);
    listen(input, "keydown", function (event) {
      if (event.key !== "Enter" || event.isComposing) return;
      var first = results.find(function (result) { return !result.hidden; });
      if (first) { event.preventDefault(); first.querySelector("a").click(); }
    });
    filter();
    search.hidden = false;
  }

  function setupHeadlines() {
    var card = document.querySelector('[data-layout="headlines"]');
    if (!card) return;
    var slides = all("article", card);
    var controls = card.querySelector('[data-layout="headline-controls"]');
    var toggle = controls.querySelector("button");
    var pause = toggle.querySelector('[data-qx="pause"]');
    var play = toggle.querySelector('[data-qx="play"]');
    var segments = all('[data-qx="segment"]', controls);
    var current = 0;
    var elapsed = 0;
    var previous;
    var playing = false;
    var interacted = false;
    var toggleWasPlaying = null;
    var request = null;

    function display() {
      slides.forEach(function (slide, index) { slide.hidden = index !== current; });
      segments.forEach(function (segment, index) {
        segment.setAttribute("aria-pressed", String(index === current));
        segment.style.setProperty("--qx-progress", index === current ? String(elapsed / 6000) : "0");
      });
      pause.hidden = !playing;
      play.hidden = playing;
      toggle.setAttribute("aria-disabled", String(reduced.matches));
    }
    function stop() {
      playing = false;
      if (request !== null) { window.cancelAnimationFrame(request); frames.delete(request); request = null; }
      display();
    }
    stopHeadlines = stop;
    function tick(time) {
      if (!playing || reduced.matches) { stop(); return; }
      if (previous !== undefined) elapsed += time - previous;
      previous = time;
      if (elapsed >= 6000) {
        elapsed = 0;
        current += 1;
        if (current === slides.length) { current = 0; stop(); return; }
        display();
      }
      segments[current].style.setProperty("--qx-progress", String(elapsed / 6000));
      request = frame(tick);
    }
    function start() {
      if (reduced.matches || playing) return;
      previous = undefined;
      playing = true;
      display();
      request = frame(tick);
    }
    function interact() { interacted = true; stop(); }
    listen(card, "pointerdown", function (event) {
      toggleWasPlaying = toggle.contains(event.target) ? playing : null;
      interact();
    });
    listen(card, "focusin", interact);
    listen(card, "click", function (event) {
      if (!toggle.contains(event.target)) interact();
    });
    listen(toggle, "click", function () {
      var resume = toggleWasPlaying === null ? !playing : !toggleWasPlaying;
      toggleWasPlaying = null;
      interact();
      if (resume) start();
    });
    segments.forEach(function (segment, index) {
      listen(segment, "click", function () { interact(); current = index; elapsed = 0; display(); });
    });
    controls.hidden = false;
    display();
    // Share the card's visibility trigger with its border sweep.
    var sweep = pending.get(card);
    onceVisible(card, function () { if (sweep) sweep(); if (!interacted) start(); });
  }

  function setupAccordions() {
    var toggles = all("[data-accordion-toggle]");
    function layout() {
      toggles.forEach(function (toggle) {
        var content = document.getElementById(toggle.getAttribute("aria-controls"));
        content.hidden = phone.matches;
        toggle.setAttribute("aria-expanded", String(!phone.matches));
        toggle.setAttribute("aria-disabled", String(!phone.matches));
      });
    }
    toggles.forEach(function (toggle) {
      listen(toggle, "click", function () {
        if (!phone.matches) return;
        var content = document.getElementById(toggle.getAttribute("aria-controls"));
        content.hidden = !content.hidden;
        toggle.setAttribute("aria-expanded", String(!content.hidden));
      });
    });
    listen(phone, "change", layout);
    layout();
  }

  function setupRail() {
    var rail = document.querySelector('[data-layout="rail-links"]');
    if (!rail) return;
    var links = all("a", rail);
    var cards = links.map(function (link) { return document.getElementById(link.hash.slice(1)); });
    var current = -1;
    var queued = false;
    function update() {
      queued = false;
      var most = 0;
      var chosen = -1;
      cards.forEach(function (card, index) {
        var box = card.getBoundingClientRect();
        var visible = Math.max(0, Math.min(box.bottom, window.innerHeight) - Math.max(box.top, 0));
        if (visible > most) { most = visible; chosen = index; }
      });
      if (chosen === current) return;
      current = chosen;
      links.forEach(function (link, index) {
        if (index === chosen) link.setAttribute("aria-current", "true");
        else link.removeAttribute("aria-current");
      });
      if (phone.matches && chosen !== -1) {
        var pill = links[chosen].getBoundingClientRect();
        var row = rail.getBoundingClientRect();
        var shift = pill.left < row.left ? pill.left - row.left : Math.max(0, pill.right - row.right);
        if (shift) rail.scrollTo({ left: rail.scrollLeft + shift, behavior: reduced.matches ? "auto" : "smooth" });
      }
    }
    function queue() { if (!queued) { queued = true; frame(update); } }
    listen(window, "scroll", queue, { passive: true });
    listen(window, "resize", queue);
    listen(document, "click", queue);
    update();
  }

  function setupSpotlights() {
    all('[data-layout="tile-grid"] > a, [data-layout="cards"] > section, [data-layout="headline"], [data-layout="headlines"]').forEach(function (node) {
      node.classList.add("qx-interactive");
      listen(node, "pointermove", function (event) {
        if (!fine.matches || reduced.matches) return;
        var box = node.getBoundingClientRect();
        node.style.setProperty("--qx-pointer-x", String(event.clientX - box.left) + "px");
        node.style.setProperty("--qx-pointer-y", String(event.clientY - box.top) + "px");
        node.classList.add("qx-spotlight");
      });
      listen(node, "pointerleave", function () { node.classList.remove("qx-spotlight"); });
    });
  }

  guard(function () {
    var attributes = ["class", "style", "hidden", "aria-expanded", "aria-disabled", "aria-current", "aria-pressed"];
    originals = all("body, body *").map(function (node) {
      return { node: node, attributes: attributes.map(function (name) { return [name, node.getAttribute(name)]; }) };
    });
    reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    fine = window.matchMedia("(hover: hover) and (pointer: fine)");
    phone = window.matchMedia("(max-width: 639px)");
    setupAccordions();
    setupMotion();
    setupSearch();
    setupHeadlines();
    setupRail();
    setupSpotlights();
    listen(reduced, "change", function () {
      if (!reduced.matches) return;
      running.forEach(function (finish) { finish(); });
      pending.clear();
      if (observer) observer.disconnect();
      all(".qx-spotlight").forEach(function (node) { node.classList.remove("qx-spotlight"); });
      motionClasses.forEach(function (name) {
        all("." + name).forEach(function (node) { node.classList.remove(name); });
      });
      stopHeadlines();
    });
  })();
}());
