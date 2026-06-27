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

  // Smooth-scroll in-page anchor links (e.g. the hero "Browse the prayers" CTA).
  // Backs up the CSS `scroll-behavior: smooth`, and honours reduced-motion by
  // simply not intercepting (the browser then jumps instantly).
  function initSmoothScroll() {
    if (
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    ) {
      return;
    }
    var links = Array.prototype.slice.call(
      document.querySelectorAll('a[href^="#"]:not(.skip-link)')
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

  function init() {
    initSearch();
    initSmoothScroll();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
