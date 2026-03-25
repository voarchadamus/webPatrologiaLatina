(() => {
  const body = document.body;
  if (!body) return;

  function q(sel, root) {
    return (root || document).querySelector(sel);
  }
  function qa(sel, root) {
    return Array.from((root || document).querySelectorAll(sel));
  }

  // ── Source lookup ─────────────────────────────────────────────────────────

  function getSourceHtml(sourceId) {
    if (!sourceId) return null;
    const el = document.getElementById(sourceId);
    if (!el) return null;
    return el.innerHTML;
  }

  // ── Inline-view helpers ───────────────────────────────────────────────────

  function updateNoteAnchors(root, enabled) {
    qa("[data-note-anchor]", root).forEach(function (anchor) {
      const sourceId = anchor.getAttribute("data-note-source");
      const sourceHtml = getSourceHtml(sourceId);
      const host = q(".note-inline-host", anchor);
      if (sourceHtml === null || !host) return;
      if (enabled) {
        host.innerHTML =
          '<small class="note note-inline-visible">[Note: ' +
          sourceHtml +
          "]</small>";
        // If figures are also active, populate any ornament anchors in the
        // freshly-injected note content (they weren't in the DOM before).
        if (body.classList.contains("show-all-figures")) {
          updateOrnamentAnchors(host, true);
        }
      } else {
        host.innerHTML = "";
      }
    });
  }

  function updateOrnamentAnchors(root, enabled) {
    qa("[data-ornament-anchor]", root).forEach(function (anchor) {
      const sourceId = anchor.getAttribute("data-ornament-inline-source");
      const sourceHtml = getSourceHtml(sourceId);
      const host = q(".ornament-inline-host", anchor);
      if (sourceHtml === null || !host) return;
      host.innerHTML = enabled ? sourceHtml : "";
    });
  }

  function applyActiveInlineViews(root) {
    updateNoteAnchors(root, body.classList.contains("show-all-notes"));
    updateOrnamentAnchors(root, body.classList.contains("show-all-figures"));
  }

  const TEXT_FONT_STORAGE_KEY = "pl-tree-text-font";
  const THEME_STORAGE_KEY = "pl-tree-theme";

  function normalizeTextFont(value) {
    return value === "centaur" ? "centaur" : "garamontio";
  }

  function readStoredTextFont() {
    try {
      return normalizeTextFont(
        window.localStorage.getItem(TEXT_FONT_STORAGE_KEY),
      );
    } catch (_error) {
      return null;
    }
  }

  function writeStoredTextFont(value) {
    try {
      window.localStorage.setItem(TEXT_FONT_STORAGE_KEY, value);
    } catch (_error) {
      // Ignore storage failures and keep the in-memory selection.
    }
  }

  // ── NOTE rewiring (task 3.1) ──────────────────────────────────────────────
  // Each .pl-node[data-tag="NOTE"][id] div is replaced with a chip button
  // whose overlay template contains the original note content.
  //
  // Title: "{TYPE} {N}" (e.g. "Lectiones Variantes (3)")
  // Button text: "Note {N}" (e.g. "Note (3)")
  // data-note-type is stored by Python on the .note-label span.

  function noteHasMeaningfulContent(noteDiv) {
    const clone = noteDiv.cloneNode(true);
    qa(".node-label, .note-label, .run-tag, .run-sep, .run-ord", clone).forEach(
      function (node) {
        node.remove();
      },
    );
    if (q("[data-ornament-anchor], img, table, .col", clone)) {
      return true;
    }
    return (clone.textContent || "").replace(/\s+/g, " ").trim().length > 0;
  }

  function rewireNotes() {
    qa('.pl-node[data-tag="NOTE"][id]').forEach(function (noteDiv) {
      if (!noteHasMeaningfulContent(noteDiv)) {
        noteDiv.remove();
        return;
      }

      const noteId = noteDiv.id;
      const labelEl = q(".note-label", noteDiv);
      const labelText = labelEl ? labelEl.textContent.trim() : "";
      const noteType = labelEl
        ? labelEl.getAttribute("data-note-type") || ""
        : "";

      // Build display strings
      const chipTitle =
        noteType && labelText
          ? noteType + " " + labelText
          : noteType || (labelText ? "Note " + labelText : "Note");
      const buttonText = labelText ? "Note " + labelText : noteType || "note";

      // Move note content to a <template> appended to <body>
      const tmpl = document.createElement("template");
      tmpl.id = noteId;
      tmpl.className = "overlay-source overlay-source-note";
      tmpl.innerHTML = noteDiv.innerHTML;
      body.appendChild(tmpl);

      // Build the note anchor: chip + inline host
      const anchor = document.createElement("span");
      anchor.className = "note-anchor";
      anchor.setAttribute("data-note-anchor", "");
      anchor.setAttribute("data-note-source", noteId);

      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "overlay-chip overlay-chip-note";
      chip.setAttribute("data-overlay-source", noteId);
      chip.setAttribute("data-overlay-title", chipTitle);
      chip.setAttribute("aria-haspopup", "dialog");
      chip.setAttribute("aria-label", chipTitle);
      chip.textContent = buttonText;

      const inlineHost = document.createElement("span");
      inlineHost.className = "note-inline-host";

      anchor.appendChild(chip);
      anchor.appendChild(inlineHost);

      noteDiv.replaceWith(anchor);
    });
  }

  // ── Overlay machinery ─────────────────────────────────────────────────────

  const overlayRoot = q("[data-overlay-root]");
  const overlayContent = overlayRoot
    ? q(".overlay-panel-content", overlayRoot)
    : null;
  let overlayStack = [];
  let currentOverlayState = null;
  let lastTrigger = null;

  function setOverlayContent(sourceId, title) {
    if (!overlayContent) return false;
    const sourceHtml = getSourceHtml(sourceId);
    if (sourceHtml === null) return false;

    overlayContent.innerHTML = "";

    const entry = document.createElement("section");
    entry.className = "overlay-entry";

    const heading = document.createElement("h3");
    heading.className = "overlay-entry-title";
    heading.textContent = title || "Detail";
    entry.appendChild(heading);

    const bodyWrapper = document.createElement("div");
    bodyWrapper.className = "overlay-entry-body";
    bodyWrapper.innerHTML = sourceHtml;
    entry.appendChild(bodyWrapper);

    overlayContent.appendChild(entry);
    applyActiveInlineViews(overlayContent);
    return true;
  }

  function renderOverlayState(state) {
    if (
      !overlayRoot ||
      state === null ||
      !setOverlayContent(state.sourceId, state.title)
    ) {
      return false;
    }
    overlayRoot.hidden = false;
    body.classList.add("overlay-open");
    const closeButton = q(".overlay-close", overlayRoot);
    if (closeButton) closeButton.focus();
    return true;
  }

  function openOverlay(sourceId, title, trigger) {
    if (!overlayRoot) return;
    const nextState = { sourceId: sourceId, title: title };
    if (overlayRoot.hidden) {
      overlayStack = [];
      lastTrigger = trigger || null;
    } else if (currentOverlayState !== null) {
      overlayStack.push(currentOverlayState);
    }
    currentOverlayState = nextState;
    renderOverlayState(nextState);
  }

  function closeOverlay() {
    if (!overlayRoot || overlayRoot.hidden) return;
    if (overlayStack.length > 0) {
      currentOverlayState = overlayStack.pop() || null;
      if (currentOverlayState !== null) {
        renderOverlayState(currentOverlayState);
        return;
      }
    }
    overlayRoot.hidden = true;
    if (overlayContent) overlayContent.innerHTML = "";
    body.classList.remove("overlay-open");
    currentOverlayState = null;
    overlayStack = [];
    if (lastTrigger) {
      lastTrigger.focus();
      lastTrigger = null;
    }
  }

  // ── Show-all toggles ──────────────────────────────────────────────────────

  function setShowAllNotes(enabled) {
    body.classList.toggle("show-all-notes", enabled);
    updateNoteAnchors(document, enabled);
    const toggle = q("[data-note-toggle]");
    if (toggle) toggle.checked = enabled;
  }

  function setShowAllFigures(enabled) {
    body.classList.toggle("show-all-figures", enabled);
    updateOrnamentAnchors(document, enabled);
    const toggle = q("[data-ornament-toggle]");
    if (toggle) toggle.checked = enabled;
  }

  function setShowContents(enabled) {
    const tocNav = q("#ebt-toc");
    const toggle = q("[data-toc-toggle]");
    if (toggle) toggle.checked = enabled;
    if (tocNav) {
      tocNav.hidden = !enabled || tocNav.childElementCount === 0;
    }
  }

  function setTextFont(value, persist) {
    const normalized = normalizeTextFont(value);
    const select = q("[data-font-select]");
    body.setAttribute("data-text-font", normalized);
    if (select) select.value = normalized;
    if (persist) writeStoredTextFont(normalized);
  }

  // ── Theme (light / dark) ──────────────────────────────────────────────────

  function readStoredTheme() {
    try {
      return window.localStorage.getItem(THEME_STORAGE_KEY) || "light";
    } catch (_e) {
      return "light";
    }
  }

  function writeStoredTheme(value) {
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, value);
    } catch (_e) {
      /* ignore */
    }
  }

  function setTheme(value, persist) {
    const dark = value === "dark";
    body.setAttribute("data-theme", dark ? "dark" : "light");
    const btn = q("[data-theme-toggle]");
    if (btn) btn.textContent = dark ? "☽" : "☉";
    if (persist) writeStoredTheme(dark ? "dark" : "light");
  }

  const themeBtn = q("[data-theme-toggle]");
  if (themeBtn) {
    themeBtn.addEventListener("click", function () {
      const isDark = body.getAttribute("data-theme") === "dark";
      setTheme(isDark ? "light" : "dark", true);
    });
  }

  const scrollTopBtn = q("[data-scroll-top]");
  if (scrollTopBtn) {
    scrollTopBtn.addEventListener("click", function () {
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }

  // ── Font size ─────────────────────────────────────────────────────────────

  const FONT_SIZE_KEY = "pl-tree-font-size";
  const FONT_SIZE_MIN = 50;
  const FONT_SIZE_MAX = 250;
  const FONT_SIZE_DEF = 150;

  function clampSize(v) {
    return Math.min(FONT_SIZE_MAX, Math.max(FONT_SIZE_MIN, v));
  }

  function readStoredFontSize() {
    try {
      const v = parseInt(window.localStorage.getItem(FONT_SIZE_KEY), 10);
      return isNaN(v) ? FONT_SIZE_DEF : clampSize(v);
    } catch (_e) {
      return FONT_SIZE_DEF;
    }
  }

  function applyFontSize(pct, persist) {
    const input = q("[data-size-input]");
    document.documentElement.style.fontSize = pct + "%";
    if (input) input.value = pct;
    if (persist) {
      try {
        window.localStorage.setItem(FONT_SIZE_KEY, pct);
      } catch (_e) {
        /* ignore */
      }
    }
  }

  const sizeInput = q("[data-size-input]");
  if (sizeInput) {
    applyFontSize(readStoredFontSize(), false);
    sizeInput.addEventListener("change", function () {
      const v = clampSize(parseInt(sizeInput.value, 10) || FONT_SIZE_DEF);
      applyFontSize(v, true);
    });
  }

  // ── Column width ──────────────────────────────────────────────────────────

  const WIDTH_KEY = "pl-tree-width";
  const WIDTH_MIN = 20;
  const WIDTH_MAX = 120;
  const WIDTH_DEF = 72;

  function clampWidth(v) {
    return Math.min(WIDTH_MAX, Math.max(WIDTH_MIN, v));
  }

  function readStoredWidth() {
    try {
      const v = parseInt(window.localStorage.getItem(WIDTH_KEY), 10);
      return isNaN(v) ? WIDTH_DEF : clampWidth(v);
    } catch (_e) {
      return WIDTH_DEF;
    }
  }

  function applyWidth(rem, persist) {
    const input = q("[data-width-input]");
    if (rem === WIDTH_DEF) {
      body.style.removeProperty("--content-width");
    } else {
      body.style.setProperty("--content-width", rem + "rem");
    }
    if (input) input.value = rem;
    if (persist) {
      try {
        window.localStorage.setItem(WIDTH_KEY, rem);
      } catch (_e) {
        /* ignore */
      }
    }
  }

  const widthInput = q("[data-width-input]");
  if (widthInput) {
    applyWidth(readStoredWidth(), false);
    widthInput.addEventListener("change", function () {
      const v = clampWidth(parseInt(widthInput.value, 10) || WIDTH_DEF);
      applyWidth(v, true);
    });
  }

  // ── Note toggle ───────────────────────────────────────────────────────────

  const noteToggle = q("[data-note-toggle]");
  if (noteToggle) {
    noteToggle.addEventListener("change", function () {
      setShowAllNotes(noteToggle.checked);
    });
  }

  // ── Text font toggle ──────────────────────────────────────────────────────

  const fontSelect = q("[data-font-select]");
  if (fontSelect) {
    fontSelect.addEventListener("change", function () {
      setTextFont(fontSelect.value, true);
    });
  }

  // ── Figure toggle ─────────────────────────────────────────────────────────

  const ornamentToggle = q("[data-ornament-toggle]");
  if (ornamentToggle) {
    ornamentToggle.addEventListener("change", function () {
      setShowAllFigures(ornamentToggle.checked);
    });
  }

  // ── Contents toggle ───────────────────────────────────────────────────────

  const tocToggle = q("[data-toc-toggle]");
  if (tocToggle) {
    tocToggle.addEventListener("change", function () {
      setShowContents(tocToggle.checked);
    });
  }

  // ── Table of contents ─────────────────────────────────────────────────────

  function getTocRoot() {
    return q("article") || q("main.pl-tree");
  }

  function getTocHeadingText(heading) {
    const clone = heading.cloneNode(true);
    qa(
      "template, .node-label, .run-tag, .run-sep, .run-ord, .note-label, " +
        ".overlay-chip, .note-inline-host, .ornament-inline-host, " +
        "[data-note-anchor], [data-ornament-anchor]",
      clone,
    ).forEach(function (node) {
      node.remove();
    });
    return (clone.textContent || "")
      .replace(/\[Col\.\s*\S+\]\s*/g, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function getTocLevelClass(heading) {
    if (heading.matches("h2.doc-title")) return "toc-level-h2";
    if (heading.matches("h3.section-meta-title")) return "toc-level-h3";
    if (heading.closest('.pl-div2, .pl-node[data-tag="DIV2"]'))
      return "toc-level-h4";
    return "toc-level-h3";
  }

  function scrollTocItemIntoView(item) {
    const tocList = q("#ebt-toc-list");
    if (!tocList) return;
    const itemRect = item.getBoundingClientRect();
    const listRect = tocList.getBoundingClientRect();
    if (itemRect.top < listRect.top) {
      tocList.scrollBy({
        top: itemRect.top - listRect.top - 8,
        behavior: "instant",
      });
    } else if (itemRect.bottom > listRect.bottom) {
      tocList.scrollBy({
        top: itemRect.bottom - listRect.bottom + 8,
        behavior: "instant",
      });
    }
  }

  function buildToc() {
    const tocNav = q("#ebt-toc");
    const tocRoot = getTocRoot();
    if (!tocNav || !tocRoot) return [];

    tocNav.innerHTML = "";

    const headings = qa(
      'h2.doc-title, h3.section-meta-title, .pl-head, .pl-node[data-tag="HEAD"]',
      tocRoot,
    )
      .map(function (heading) {
        return {
          heading: heading,
          text: getTocHeadingText(heading),
        };
      })
      .filter(function (entry) {
        return entry.text.length > 0;
      });

    if (headings.length < 2) return [];

    let idCounter = 0;
    headings.forEach(function (entry) {
      if (entry.heading.id) return;
      let nextId = "";
      do {
        nextId = "toc-h-" + idCounter++;
      } while (document.getElementById(nextId));
      entry.heading.id = nextId;
    });

    const list = document.createElement("ol");
    list.id = "ebt-toc-list";
    list.className = "toc-list";

    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "toc-toggle";
    toggle.setAttribute("aria-expanded", "true");
    toggle.setAttribute("aria-controls", list.id);
    toggle.textContent = "ToC";

    toggle.addEventListener("click", function () {
      const expanded = toggle.getAttribute("aria-expanded") === "true";
      const nextExpanded = !expanded;
      toggle.setAttribute("aria-expanded", String(nextExpanded));
      list.hidden = !nextExpanded;
    });

    const tocItems = headings.map(function (entry) {
      const item = document.createElement("li");
      item.className = "toc-item " + getTocLevelClass(entry.heading);
      const link = document.createElement("a");
      link.href = "#" + entry.heading.id;
      link.className = "toc-link";
      link.textContent = entry.text;
      link.addEventListener("click", function (event) {
        event.preventDefault();
        const elementPosition =
          entry.heading.getBoundingClientRect().top + window.scrollY;
        const offsetPosition = elementPosition - window.innerHeight * 0.25;
        window.scrollTo({ top: offsetPosition, behavior: "instant" });
        if (history.pushState) {
          history.pushState(null, "", "#" + entry.heading.id);
        }
      });
      item.appendChild(link);
      list.appendChild(item);
      return { heading: entry.heading, item: item, link: link };
    });

    tocNav.appendChild(toggle);
    tocNav.appendChild(list);
    return tocItems;
  }

  function trackActiveTocItem(tocItems) {
    if (!tocItems.length) return;

    let lastActiveId = null;

    function updateActive() {
      const threshold = window.innerHeight * 0.251;
      let activeId = null;

      for (let i = 0; i < tocItems.length; i += 1) {
        const item = tocItems[i];
        if (item.heading.getBoundingClientRect().top <= threshold) {
          activeId = item.heading.id;
        } else {
          break;
        }
      }

      if (activeId === lastActiveId) return;
      lastActiveId = activeId;

      tocItems.forEach(function (item) {
        const isActive =
          activeId !== null &&
          item.link.getAttribute("href") === "#" + activeId;
        if (isActive) {
          item.item.classList.add("toc-active");
          scrollTocItemIntoView(item.item);
        } else {
          item.item.classList.remove("toc-active");
        }
      });
    }

    window.addEventListener("scroll", updateActive, { passive: true });
    window.addEventListener("resize", updateActive, { passive: true });
    updateActive();
  }

  // ── Event delegation ──────────────────────────────────────────────────────

  document.addEventListener("click", function (event) {
    const trigger = event.target.closest("[data-overlay-source]");
    if (trigger) {
      event.preventDefault();
      openOverlay(
        trigger.getAttribute("data-overlay-source"),
        trigger.getAttribute("data-overlay-title") ||
          trigger.textContent ||
          "Detail",
        trigger,
      );
      return;
    }
    if (event.target.closest("[data-overlay-close]")) {
      event.preventDefault();
      closeOverlay();
    }
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") closeOverlay();
  });

  // ── Initialise ────────────────────────────────────────────────────────────

  rewireNotes();
  applyActiveInlineViews(document);
  setTextFont(
    readStoredTextFont() || (fontSelect ? fontSelect.value : "garamontio"),
    false,
  );
  setTheme(readStoredTheme(), false);
  const tocItems = buildToc();
  setShowContents(tocToggle ? tocToggle.checked : true);
  trackActiveTocItem(tocItems);
})();
