/* latinprayers.org — progressive enhancement only.
 *
 * The site is fully readable and navigable with JavaScript disabled. This adds
 * one optional nicety: a client-side filter over the homepage prayer index.
 * It degrades gracefully — the search field is hidden in the markup and only
 * revealed here, so a visitor without JS sees the full, unfiltered list.
 */
(function () {
  "use strict";

  function initSearch() {
    var form = document.querySelector(".prayer-search");
    var input = document.getElementById("prayer-search-input");
    if (!form || !input) return;

    var status = form.querySelector(".prayer-search-status");
    var cards = Array.prototype.slice.call(
      document.querySelectorAll(".prayer-list > li")
    );
    var sections = Array.prototype.slice.call(
      document.querySelectorAll(".category")
    );
    if (!cards.length) return;

    // Reveal the search now that the enhancement is active.
    form.hidden = false;

    function apply() {
      var query = input.value.trim().toLowerCase();
      var tokens = query ? query.split(/\s+/) : [];
      var visible = 0;

      // Every token must appear somewhere in a card's data-search haystack
      // (Latin name + English gloss + category), so "hail latin" narrows.
      cards.forEach(function (li) {
        var haystack = li.getAttribute("data-search") || "";
        var match = tokens.every(function (token) {
          return haystack.indexOf(token) !== -1;
        });
        li.hidden = !match;
        if (match) visible += 1;
      });

      // Hide a category heading when all of its prayers are filtered out.
      sections.forEach(function (section) {
        section.hidden = !section.querySelector(
          ".prayer-list > li:not([hidden])"
        );
      });

      if (!tokens.length) {
        status.textContent = "";
      } else if (visible === 0) {
        status.textContent = "No prayers match “" + input.value.trim() + "”.";
      } else {
        status.textContent =
          visible + (visible === 1 ? " prayer" : " prayers") + " found.";
      }
    }

    input.addEventListener("input", apply);
    input.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && input.value) {
        input.value = "";
        apply();
      }
    });
    // The filter is live; the form should never submit or reload the page.
    form.addEventListener("submit", function (e) {
      e.preventDefault();
    });
  }

  // The Mysteries toggle. The markup has three anchor "tabs" and three panels,
  // all visible by default (fully readable with no JS). This upgrades them into
  // a single-select tab group and opens the set proper to today's weekday.
  function initMysteries() {
    var section = document.querySelector(".mysteries");
    if (!section) return;
    var tablist = section.querySelector(".mysteries-tabs");
    var tabs = Array.prototype.slice.call(
      section.querySelectorAll(".mysteries-tab")
    );
    var panels = Array.prototype.slice.call(
      section.querySelectorAll(".mysteries-panel")
    );
    if (tabs.length < 2 || !panels.length) return;

    section.classList.add("js-mysteries");
    if (tablist) tablist.setAttribute("role", "tablist");

    function panelFor(tab) {
      return document.getElementById(tab.getAttribute("aria-controls"));
    }

    function select(tab, focus) {
      tabs.forEach(function (t) {
        var on = t === tab;
        t.setAttribute("aria-selected", on ? "true" : "false");
        t.setAttribute("tabindex", on ? "0" : "-1");
        var panel = panelFor(t);
        if (panel) panel.hidden = !on;
      });
      if (focus) tab.focus();
    }

    tabs.forEach(function (tab, i) {
      tab.setAttribute("role", "tab");
      var panel = panelFor(tab);
      if (panel) panel.setAttribute("role", "tabpanel");

      tab.addEventListener("click", function (e) {
        e.preventDefault();
        select(tab, false);
      });
      tab.addEventListener("keydown", function (e) {
        var dir = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
        if (!dir) return;
        e.preventDefault();
        select(tabs[(i + dir + tabs.length) % tabs.length], true);
      });
    });

    // Default selection: a matching URL hash wins; otherwise today's set
    // (data-days carries the weekday numbers, 0=Sun…6=Sat); else the first tab.
    var def = tabs[0];
    var hash = window.location.hash.replace("#", "");
    var fromHash = hash
      ? tabs.filter(function (t) {
          return t.getAttribute("aria-controls") === hash;
        })[0]
      : null;
    if (fromHash) {
      def = fromHash;
    } else {
      var today = String(new Date().getDay());
      tabs.forEach(function (t) {
        if ((t.getAttribute("data-days") || "").split(",").indexOf(today) !== -1) {
          def = t;
        }
      });
    }
    select(def, false);
  }

  // Decade carousels: each set's five mysteries sit in a horizontal scroll-snap
  // track (swipeable on its own with no JS). This adds prev/next + dot controls
  // and hides the scrollbar; the track stays the single source of position.
  function initCarousels() {
    var reduce =
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var carousels = Array.prototype.slice.call(
      document.querySelectorAll(".decade-carousel")
    );

    carousels.forEach(function (carousel) {
      var track = carousel.querySelector(".decade-track");
      if (!track) return;
      var cards = Array.prototype.slice.call(
        track.querySelectorAll(".decade-card")
      );
      if (cards.length < 2) return;

      carousel.classList.add("js-carousel");

      var controls = document.createElement("div");
      controls.className = "decade-controls";

      var prev = document.createElement("button");
      prev.type = "button";
      prev.className = "decade-nav decade-prev";
      prev.setAttribute("aria-label", "Previous mystery");
      prev.innerHTML = "‹";

      var next = document.createElement("button");
      next.type = "button";
      next.className = "decade-nav decade-next";
      next.setAttribute("aria-label", "Next mystery");
      next.innerHTML = "›";

      var dotsWrap = document.createElement("div");
      dotsWrap.className = "decade-dots";
      var dots = cards.map(function (card, i) {
        var dot = document.createElement("button");
        dot.type = "button";
        dot.className = "decade-dot";
        dot.setAttribute("aria-label", "Mystery " + (i + 1));
        dot.addEventListener("click", function () {
          go(i);
        });
        dotsWrap.appendChild(dot);
        return dot;
      });

      controls.appendChild(prev);
      controls.appendChild(dotsWrap);
      controls.appendChild(next);
      carousel.appendChild(controls);

      var index = 0;

      function liveIndex() {
        var best = 0;
        var min = Infinity;
        for (var i = 0; i < cards.length; i++) {
          var dist = Math.abs(cards[i].offsetLeft - track.scrollLeft);
          if (dist < min) {
            min = dist;
            best = i;
          }
        }
        return best;
      }

      function paint(i) {
        for (var j = 0; j < dots.length; j++) {
          dots[j].setAttribute("aria-current", j === i ? "true" : "false");
        }
        prev.disabled = i <= 0;
        next.disabled = i >= cards.length - 1;
      }

      // Buttons drive a canonical index so rapid clicks chain even mid-scroll;
      // a manual swipe re-syncs that index once the scroll settles. While a
      // button-driven scroll is animating, `programmatic` keeps the target dot
      // lit instead of flashing back to the position the scroll is passing.
      var programmatic = false;
      function go(i) {
        index = Math.max(0, Math.min(cards.length - 1, i));
        programmatic = true;
        track.scrollTo({
          left: cards[index].offsetLeft,
          behavior: reduce ? "auto" : "smooth"
        });
        paint(index);
      }

      prev.addEventListener("click", function () {
        go(index - 1);
      });
      next.addEventListener("click", function () {
        go(index + 1);
      });

      var ticking = false;
      var settle;
      track.addEventListener("scroll", function () {
        if (!ticking) {
          ticking = true;
          requestAnimationFrame(function () {
            ticking = false;
            if (!programmatic) paint(liveIndex());
          });
        }
        clearTimeout(settle);
        settle = setTimeout(function () {
          programmatic = false;
          index = liveIndex();
          paint(index);
        }, 120);
      });

      paint(0);
    });
  }

  // Smooth-scroll in-page anchor links (e.g. the hero "Browse the prayers" CTA).
  // Backs up the CSS `scroll-behavior: smooth`, and honours reduced-motion by
  // simply not intercepting (the browser then jumps instantly). The Mysteries
  // tabs are excluded — they switch panels rather than scroll.
  function initSmoothScroll() {
    if (
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    ) {
      return;
    }
    var links = Array.prototype.slice.call(
      document.querySelectorAll('a[href^="#"]:not(.skip-link):not(.mysteries-tab)')
    );
    links.forEach(function (link) {
      link.addEventListener("click", function (e) {
        var id = link.getAttribute("href").slice(1);
        if (!id) return;
        var target = document.getElementById(id);
        if (!target) return;
        e.preventDefault();
        // scrollIntoView respects the target's scroll-margin-top, so it clears
        // the sticky masthead.
        target.scrollIntoView({ behavior: "smooth", block: "start" });
        if (history.replaceState) history.replaceState(null, "", "#" + id);
      });
    });
  }

  // Copy the Latin text of a prayer. Progressive enhancement: the button is
  // created here, so a no-JS visitor never sees a dead control. The Latin lives
  // as <br>-separated lines in .prayer-latin .prayer-text (the drop-cap is a
  // ::first-letter pseudo, so it isn't in the DOM and doesn't interfere).
  var CLIPBOARD_SVG =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="3" width="6" height="4" rx="1"></rect><path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"></path></svg>';
  var CHECK_SVG =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5"></path></svg>';

  function latinTextFrom(el) {
    // Split on the <br> line breaks, then let the browser decode entities and
    // strip any incidental markup by reading textContent per line.
    var decoder = document.createElement("div");
    return el.innerHTML
      .split(/<br\s*\/?>/i)
      .map(function (part) {
        decoder.innerHTML = part;
        return (decoder.textContent || "").replace(/\s+/g, " ").trim();
      })
      .filter(function (line) {
        return line.length;
      })
      .join("\n");
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    // Fallback for browsers without the async clipboard API.
    return new Promise(function (resolve, reject) {
      try {
        var ta = document.createElement("textarea");
        ta.value = text;
        ta.setAttribute("readonly", "");
        ta.style.position = "fixed";
        ta.style.top = "-9999px";
        document.body.appendChild(ta);
        ta.select();
        var ok = document.execCommand("copy");
        document.body.removeChild(ta);
        ok ? resolve() : reject();
      } catch (e) {
        reject(e);
      }
    });
  }

  function initCopyLatin() {
    var latin = document.querySelector(".prayer-latin .prayer-text");
    var body = document.querySelector(".prayer-body");
    if (!latin || !body) return;
    var text = latinTextFrom(latin);
    if (!text) return;

    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "copy-latin";
    btn.setAttribute("aria-label", "Copy the Latin text");

    function render(label, svg) {
      btn.innerHTML = svg + '<span class="copy-latin-label">' + label + "</span>";
    }
    render("Copy Latin", CLIPBOARD_SVG);

    var revert;
    btn.addEventListener("click", function () {
      copyText(text).then(
        function () {
          btn.classList.add("is-copied");
          render("Copied", CHECK_SVG);
          clearTimeout(revert);
          revert = setTimeout(function () {
            btn.classList.remove("is-copied");
            render("Copy Latin", CLIPBOARD_SVG);
          }, 1800);
        },
        function () {
          render("Press ⌘/Ctrl + C", CLIPBOARD_SVG);
        }
      );
    });

    // A single meta row beneath the card: the copy action on the left, and the
    // existing "Translation source" line (when present) pulled up onto its right.
    var actions = document.createElement("div");
    actions.className = "prayer-actions";
    actions.appendChild(btn);
    body.insertAdjacentElement("afterend", actions);

    var source = document.querySelector(".prayer-source");
    if (source) actions.appendChild(source);
  }

  function init() {
    initSearch();
    initMysteries();
    initCarousels();
    initSmoothScroll();
    initCopyLatin();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
