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
    var index = document.getElementById("prayers");
    var empty = document.querySelector(".prayer-empty");
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

      // "Showing" carries the point that a list is being filtered — the
      // connection the layout cannot make on its own, since the field is in the
      // dark band and the list it filters is in the section below. The total is
      // left out: it dates as the collection grows, and a small number beside
      // the result undersells a collection that is still being added to.
      if (!tokens.length) {
        status.textContent = "";
      } else if (visible === 0) {
        status.textContent = "No prayers match “" + input.value.trim() + "”.";
      } else {
        status.textContent =
          "Showing " + visible + (visible === 1 ? " prayer" : " prayers");
      }
      form.classList.toggle("is-filtering", tokens.length > 0);

      // With every category hidden there is nothing between the field and the
      // closing note, so the note becomes the answer to the failed search. This
      // says so in words first, and pulls the two together into one message.
      var none = tokens.length > 0 && visible === 0;
      if (empty) empty.hidden = !none;
      if (index) index.classList.toggle("is-empty", none);
    }

    // The list often starts at or below the fold, so the first keystroke changes
    // something nobody can see. Pull the field to the top of the viewport once,
    // which brings the results up under it. Once only, and never when the list is
    // already in view, so it cannot fight the reader's own scrolling.
    var revealed = false;
    function reveal() {
      if (revealed) return;
      var list = document.getElementById("prayers");
      if (!list || !input.value.trim()) return;
      revealed = true;
      if (list.getBoundingClientRect().top < window.innerHeight * 0.75) return;
      var reduce = window.matchMedia &&
        window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      form.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
    }

    input.addEventListener("input", function () {
      apply();
      reveal();
    });
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

    var reduceMotion =
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    // Fade a newly opened set's card in, borrowing the carousel's own swap class
    // so the two transitions are the same length and easing. Two frames are
    // needed: an element revealed and restyled within one frame simply appears
    // at its end value, with nothing to transition from.
    function reveal(panel) {
      if (reduceMotion || !panel) return;
      var carousel = panel.querySelector(".decade-carousel");
      if (!carousel) return;
      carousel.classList.add("is-swapping");
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          carousel.classList.remove("is-swapping");
        });
      });
    }

    function select(tab, focus, animate) {
      tabs.forEach(function (t) {
        var on = t === tab;
        t.setAttribute("aria-selected", on ? "true" : "false");
        t.setAttribute("tabindex", on ? "0" : "-1");
        var panel = panelFor(t);
        if (panel) panel.hidden = !on;
      });
      if (animate) reveal(panelFor(tab));
      if (focus) tab.focus();
    }

    tabs.forEach(function (tab, i) {
      tab.setAttribute("role", "tab");
      var panel = panelFor(tab);
      if (panel) panel.setAttribute("role", "tabpanel");

      tab.addEventListener("click", function (e) {
        e.preventDefault();
        // Re-opening the set already showing would blink its card for nothing.
        select(tab, false, tab.getAttribute("aria-selected") !== "true");
      });
      tab.addEventListener("keydown", function (e) {
        var dir = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
        if (!dir) return;
        e.preventDefault();
        select(tabs[(i + dir + tabs.length) % tabs.length], true, true);
      });
    });

    // The set proper to today (data-days carries the weekday numbers, 0=Sun…6=Sat).
    // The site is static and a built page is served for days, so the day can only
    // be known here, at view time — never at build time.
    var today = String(new Date().getDay());
    var todayTab = tabs.filter(function (t) {
      return (t.getAttribute("data-days") || "").split(",").indexOf(today) !== -1;
    })[0];

    // Give that tab a "Today" chip alongside its weekday line. Which of the two
    // shows is left to CSS, keyed off the tab's own aria-selected: the chip
    // while the set is open (where it answers "should I be praying this one?"),
    // the weekdays once the reader moves to another set (where the schedule is
    // the more useful thing to read). The class is the hook for that rule.
    if (todayTab) {
      todayTab.classList.add("is-today");
      var chip = document.createElement("span");
      chip.className = "mysteries-tab-today";
      chip.textContent = "Today";
      todayTab.appendChild(chip);
    }

    // Default selection: a matching URL hash wins; otherwise today's set; else
    // the first tab.
    var hash = window.location.hash.replace("#", "");
    var fromHash = hash
      ? tabs.filter(function (t) {
          return t.getAttribute("aria-controls") === hash;
        })[0]
      : null;
    select(fromHash || todayTab || tabs[0], false);
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

      // The site's drawn arrow, as on the back link and the hero.
      var ARROW_LEFT = '<path d="M19 12H5"/><path d="M11 18l-6-6 6-6"/>';
      var ARROW_RIGHT = '<path d="M5 12h14"/><path d="M13 6l6 6-6 6"/>';
      function arrow(paths) {
        return (
          '<svg class="decade-nav-arrow" viewBox="0 0 24 24" fill="none" ' +
          'stroke="currentColor" stroke-width="2.2" stroke-linecap="round" ' +
          'stroke-linejoin="round" aria-hidden="true">' + paths + "</svg>"
        );
      }

      var prev = document.createElement("button");
      prev.type = "button";
      prev.className = "decade-nav decade-prev";
      prev.setAttribute("aria-label", "Previous mystery");
      prev.innerHTML = arrow(ARROW_LEFT) + "<span>Prev</span>";

      var next = document.createElement("button");
      next.type = "button";
      next.className = "decade-nav decade-next";
      next.setAttribute("aria-label", "Next mystery");
      next.innerHTML = "<span>Next</span>" + arrow(ARROW_RIGHT);

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
      // button-driven jump is in hand, `programmatic` keeps the target dot lit
      // instead of flashing back to the position the scroll is passing.
      var programmatic = false;
      function jump() {
        programmatic = true;
        // The track carries `scroll-behavior: smooth` in CSS, and a scrollTo of
        // `behavior: "auto"` defers to exactly that, which would animate the
        // slide we are trying to replace (invisibly, then visibly as it runs on
        // past the fade). Suspending the property for the assignment is the one
        // way to be certain the move is instantaneous.
        var behavior = track.style.scrollBehavior;
        track.style.scrollBehavior = "auto";
        track.scrollLeft = cards[index].offsetLeft;
        track.style.scrollBehavior = behavior;
      }

      // Navigating by button or dot cross-fades rather than slides: the card's
      // contents fade out, the track jumps to the next card while nothing is
      // visible, and the new contents fade in. The card's own black shell never
      // fades (every card's shell is identical, so the jump is unseen), and the
      // controls sit outside the track, so they stay put and stay legible
      // throughout. Dragging the track by hand still scrolls it as before.
      var FADE_MS = 200;
      var swap;
      function go(i) {
        index = Math.max(0, Math.min(cards.length - 1, i));
        paint(index);
        if (reduce) {
          jump();
          return;
        }
        carousel.classList.add("is-swapping");
        clearTimeout(swap);
        swap = setTimeout(function () {
          jump();
          carousel.classList.remove("is-swapping");
        }, FADE_MS);
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
  // as one or more .prayer-latin .prayer-stanza paragraphs of <br>-separated
  // lines (the drop-cap is a ::first-letter pseudo, so it isn't in the DOM and
  // doesn't interfere).
  var CLIPBOARD_SVG =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="3" width="6" height="4" rx="1"></rect><path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"></path></svg>';
  var CHECK_SVG =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5"></path></svg>';

  function stanzaTextFrom(stanzas) {
    // Each stanza is a <p> of <br>-separated lines. Split on the line breaks,
    // decode entities and strip incidental markup per line via textContent, then
    // join lines with a newline and stanzas with a blank line, so the copied
    // text preserves the same stanza breaks the reader sees.
    var decoder = document.createElement("div");
    return Array.prototype.map
      .call(stanzas, function (stanza) {
        return stanza.innerHTML
          .split(/<br\s*\/?>/i)
          .map(function (part) {
            decoder.innerHTML = part;
            return (decoder.textContent || "").replace(/\s+/g, " ").trim();
          })
          .filter(function (line) {
            return line.length;
          })
          .join("\n");
      })
      .filter(function (block) {
        return block.length;
      })
      .join("\n\n");
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

  // One copy button for one column of the prayer. Returns null when that column
  // has nothing to copy, so a prayer missing a column simply gets one button.
  // The label is the button's only accessible name: no aria-label, so what a
  // screen reader announces is exactly what is written on it, including as it
  // changes to "Copied".
  function copyButton(selector, label) {
    var stanzas = document.querySelectorAll(selector);
    if (!stanzas.length) return null;
    var text = stanzaTextFrom(stanzas);
    if (!text) return null;

    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "copy-btn";

    function render(text_, svg) {
      btn.innerHTML = svg + '<span class="copy-btn-label">' + text_ + "</span>";
    }
    render(label, CLIPBOARD_SVG);

    var revert;
    btn.addEventListener("click", function () {
      copyText(text).then(
        function () {
          btn.classList.add("is-copied");
          render("Copied", CHECK_SVG);
          clearTimeout(revert);
          revert = setTimeout(function () {
            btn.classList.remove("is-copied");
            render(label, CLIPBOARD_SVG);
          }, 1800);
        },
        function () {
          render("Press ⌘/Ctrl + C", CLIPBOARD_SVG);
        }
      );
    });
    return btn;
  }

  function initCopyButtons() {
    var body = document.querySelector(".prayer-body");
    if (!body) return;
    var buttons = [
      copyButton(".prayer-latin .prayer-stanza", "Copy Latin"),
      copyButton(".prayer-english .prayer-stanza", "Copy English")
    ].filter(Boolean);
    if (!buttons.length) return;

    // A single meta row beneath the card: the copy actions on the left, and the
    // existing "Translation source" line (when present) pulled up onto its
    // right. The buttons share a wrapper so that they stay side by side as one
    // unit when the row stacks on a phone, rather than becoming two rows.
    var actions = document.createElement("div");
    actions.className = "prayer-actions";
    var group = document.createElement("div");
    group.className = "copy-actions";
    buttons.forEach(function (btn) {
      group.appendChild(btn);
    });
    actions.appendChild(group);
    body.insertAdjacentElement("afterend", actions);

    var source = document.querySelector(".prayer-source");
    if (source) actions.appendChild(source);
  }

  // ---- Share dock ---------------------------------------------------------
  // Passing a prayer on is something a reader does once they have come through
  // it, so the control is withheld until then rather than sitting at the top of
  // the page asking early. Once earned it is kept for the rest of the visit; see
  // the reveal at the foot of this function.
  //
  // The destinations are deliberately plain: one clipboard button and two
  // ordinary links. wa.me and mailto: are navigations the reader chooses, not
  // embeds, so nothing third-party is fetched while the page is being read.
  var SHARE_SVG =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10 3.5H6A2.5 2.5 0 0 0 3.5 6v12A2.5 2.5 0 0 0 6 20.5h12a2.5 2.5 0 0 0 2.5-2.5v-4"></path><path d="M14 3.5h6.5V10"></path><path d="M20.5 3.5 9.5 14.5"></path></svg>';
  var LINK_SVG =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path></svg>';
  var MAIL_SVG =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2.5" y="4.5" width="19" height="15" rx="2.5"></rect><path d="m21.5 7.5-8.4 5.35a2 2 0 0 1-2.2 0L2.5 7.5"></path></svg>';
  // The brand mark, filled as brand marks are, held here as a path like every
  // other icon on the site rather than pulled from anyone's icon CDN.
  var WHATSAPP_SVG =
    '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.45 1.32 4.95L2 22l5.25-1.38a9.9 9.9 0 0 0 4.79 1.22h.01c5.46 0 9.9-4.45 9.9-9.91C21.95 6.45 17.5 2 12.04 2Zm0 18.15h-.01a8.2 8.2 0 0 1-4.19-1.15l-.3-.18-3.12.82.83-3.04-.2-.31a8.19 8.19 0 0 1-1.26-4.38c0-4.54 3.7-8.23 8.25-8.23a8.2 8.2 0 0 1 8.24 8.24c0 4.54-3.7 8.23-8.24 8.23Zm4.52-6.16c-.25-.12-1.47-.72-1.69-.81-.23-.08-.39-.12-.56.13-.16.24-.64.8-.78.97-.15.16-.29.18-.53.06-.25-.12-1.05-.39-1.99-1.23-.74-.66-1.23-1.47-1.38-1.72-.14-.25-.01-.38.11-.5.11-.11.25-.29.37-.44.13-.15.17-.25.25-.41.09-.17.04-.31-.02-.43-.06-.12-.56-1.34-.76-1.84-.2-.48-.41-.42-.56-.43h-.48c-.16 0-.43.06-.66.31-.22.25-.86.85-.86 2.06 0 1.22.89 2.39 1.01 2.56.12.16 1.75 2.67 4.23 3.74.59.26 1.05.41 1.41.52.6.19 1.14.16 1.57.1.48-.07 1.47-.6 1.68-1.18.21-.58.21-1.08.14-1.18-.06-.11-.22-.17-.47-.29Z"></path></svg>';

  function initShareDock() {
    var card = document.querySelector(".prayer-body");
    if (!card) return;

    // The canonical link rather than location.href: what gets passed on should
    // be the prayer's published address, whatever host it was read on.
    var canonical = document.querySelector('link[rel="canonical"]');
    var url = (canonical && canonical.href) || location.href;
    var latin = document.querySelector(".prayer-title");
    var english = document.querySelector(".prayer-subtitle");
    var name = latin ? latin.textContent.trim() : document.title;
    if (english && english.textContent.trim()) {
      name += " (" + english.textContent.trim() + ")";
    }
    var message = name + "\n" + url;

    var dock = document.createElement("div");
    dock.className = "share-dock";

    var menu = document.createElement("div");
    menu.className = "share-menu";
    menu.id = "share-menu";
    menu.hidden = true;
    var heading = document.createElement("p");
    heading.className = "share-menu-title";
    heading.textContent = "Share this prayer";
    menu.appendChild(heading);

    // Copy link. Reuses the clipboard helper the copy buttons already use, and
    // keeps the menu open afterwards so the confirmation is actually seen.
    var copyBtn = document.createElement("button");
    copyBtn.type = "button";
    copyBtn.className = "share-item";
    function renderCopy(label) {
      copyBtn.innerHTML = LINK_SVG + "<span>" + label + "</span>";
    }
    renderCopy("Copy link");
    var revert;
    copyBtn.addEventListener("click", function () {
      copyText(url).then(
        function () {
          copyBtn.classList.add("is-done");
          renderCopy("Link copied");
          clearTimeout(revert);
          revert = setTimeout(function () {
            copyBtn.classList.remove("is-done");
            renderCopy("Copy link");
          }, 1800);
        },
        function () {
          renderCopy("Press ⌘/Ctrl + C");
        }
      );
    });
    menu.appendChild(copyBtn);

    function destination(href, label, svg, newTab) {
      var a = document.createElement("a");
      a.className = "share-item";
      a.href = href;
      if (newTab) {
        a.target = "_blank";
        a.rel = "noopener noreferrer";
      }
      a.innerHTML = svg + "<span>" + label + "</span>";
      a.addEventListener("click", function () {
        close(false);
      });
      return a;
    }
    menu.appendChild(
      destination(
        "mailto:?subject=" +
          encodeURIComponent(name) +
          "&body=" +
          encodeURIComponent(message),
        "Via Email",
        MAIL_SVG,
        false
      )
    );
    menu.appendChild(
      destination(
        "https://wa.me/?text=" + encodeURIComponent(message),
        "Via WhatsApp",
        WHATSAPP_SVG,
        true
      )
    );

    var toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "share-toggle";
    // The written label is the button's only accessible name (no aria-label), so
    // what a screen reader announces is exactly what is on the button.
    toggle.innerHTML = "<span>Share</span>" + SHARE_SVG;
    toggle.setAttribute("aria-expanded", "false");
    toggle.setAttribute("aria-controls", "share-menu");

    function onKey(e) {
      if (e.key === "Escape") close(true);
    }
    function onOutside(e) {
      if (!dock.contains(e.target)) close(false);
    }
    function open() {
      menu.hidden = false;
      toggle.setAttribute("aria-expanded", "true");
      document.addEventListener("keydown", onKey);
      document.addEventListener("click", onOutside, true);
      var first = menu.querySelector(".share-item");
      if (first) first.focus();
    }
    function close(returnFocus) {
      if (menu.hidden) return;
      menu.hidden = true;
      toggle.setAttribute("aria-expanded", "false");
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("click", onOutside, true);
      if (returnFocus) toggle.focus();
    }
    toggle.addEventListener("click", function () {
      if (menu.hidden) open();
      else close(true);
    });

    dock.appendChild(menu);
    dock.appendChild(toggle);
    document.body.appendChild(dock);

    // "The prayer is finished on screen" means its copy buttons have begun to
    // appear at the foot of the viewport, which puts the whole text above the
    // reader. The button group is measured rather than the row around it: on a
    // phone that row is stacked with the translation credit above the buttons,
    // so the row's own top edge would arrive early. Where the buttons could not
    // be built at all, the foot of the card stands in for them.
    var tail = document.querySelector(".copy-actions");

    // Whichever comes first: half the page scrolled, or the end of the prayer
    // reaching the screen. A short prayer is done with well before the halfway
    // mark, so the dock arrives the moment the foot of the card (and with it the
    // copy buttons) comes into view; a long one runs past the screen, so the
    // halfway mark gets there first. Either way the dock turns up once the
    // reader has something to pass on. Read on a rAF rather than straight out of
    // the scroll event, so a fast scroll measures the layout once per frame
    // instead of once per event.
    var queued = false;
    function update() {
      queued = false;
      var scrollable =
        document.documentElement.scrollHeight - window.innerHeight;
      // A page short enough not to scroll has nothing to come through, so the
      // dock is offered straight away rather than never.
      var halfway = scrollable <= 0 || window.pageYOffset / scrollable >= 0.5;
      var prayerRead = tail
        ? tail.getBoundingClientRect().top <= window.innerHeight
        : card.getBoundingClientRect().bottom <= window.innerHeight;
      if (!halfway && !prayerRead) return;
      // Offered once, then left alone. A control that withdrew itself whenever
      // the reader scrolled back up to re-read a line would be flickering in and
      // out from under them, so this is the last measurement taken and the
      // listeners come off with it.
      dock.classList.add("is-visible");
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    }
    function onScroll() {
      if (queued) return;
      queued = true;
      requestAnimationFrame(update);
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    update();
  }

  function init() {
    initSearch();
    initMysteries();
    initCarousels();
    initSmoothScroll();
    initCopyButtons();
    initShareDock();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
