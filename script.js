const INCLUDE_BOUNDS_SESSION_KEY = "fluent-icons-include-bounds";
const PANEL_SIZE_MENU_HIDE_DELAY_MS = 130;

function getCollectionPickerOption(set, key) {
    const shortLabel = typeof set?.shortLabel === "string" ? set.shortLabel.trim() : "";
    const label = typeof set?.label === "string" ? set.label.trim() : "";

    return {
        text: shortLabel || label || key,
        title: label || key,
    };
}

function readIncludeBoundsPreference() {
    try {
        return sessionStorage.getItem(INCLUDE_BOUNDS_SESSION_KEY) === "true";
    } catch (error) {
        console.warn("Session storage is unavailable; SVG bounds will reset on reload:", error);
        return false;
    }
}

function writeIncludeBoundsPreference(enabled) {
    try {
        sessionStorage.setItem(INCLUDE_BOUNDS_SESSION_KEY, String(enabled));
    } catch (error) {
        console.warn("Session storage is unavailable; SVG bounds will reset on reload:", error);
    }
}

class IconBrowser {
    constructor() {
        this.iconSets = {};
        this.setAliases = {};
        this.currentSetKey = "fluent";
        this.currentSet = null;
        this.styleMode = "";
        this.icons = [];
        this.filteredIcons = [];
        this.currentIcon = null;
        this.selectedIconName = null;
        this.activePanelVariant = null;
        this.panelSelectedSizes = {
            regular: null,
            filled: null,
            color: null,
        };
        this.panelCurrentColorEnabled = {
            regular: false,
            filled: false,
        };
        this.includeBoundsEnabled = readIncludeBoundsPreference();
        this.iconByName = new Map();
        this.cardByName = new Map();
        this.renderedAllCards = false;
        this.lastAppliedStyleMode = null;
        this.searchDebounceTimer = null;
        this.searchDebounceMs = 120;
        this.panelSwipeGesture = null;
        this.panelSwipeAnimationTimer = null;
        this.panelSizeMenuCloseTimer = null;
        this.remoteIconSourceResolver = globalThis.RemoteIconSource
            ? new globalThis.RemoteIconSource.RemoteIconSourceResolver()
            : null;
        this.remotePreviewObserver = null;
        this.remotePreviewFallbackScheduled = false;
        this.remotePreviewRequestSequence = 0;
        this.init();
    }

    getActiveStyleMode() {
        return this.styleMode;
    }

    async init() {
        await this.loadIcons();
        this.setupEventListeners();
        this.setupFooterOffset();
        this.setupRemotePreviewHydration();
        this.applyCurrentSet();
        this.applyDeepLink();
    }

    normalizePayload(payload) {
        if (Array.isArray(payload)) {
            return {
                defaultSet: "fluent",
                setAliases: {},
                sets: {
                    fluent: {
                        label: "Fluent System Icons",
                        shortLabel: "Fluent",
                        source: "microsoft/fluentui-system-icons",
                        icons: payload,
                    },
                },
            };
        }

        if (payload && typeof payload === "object") {
            if (payload.sets && typeof payload.sets === "object") {
                return {
                    defaultSet: payload.defaultSet || "fluent",
                    setAliases: this.normalizeSetAliases(payload.setAliases),
                    sets: this.addLegacySetShortLabels(payload.sets),
                };
            }

            const icons = Array.isArray(payload.icons) ? payload.icons : [];
            return {
                defaultSet: "fluent",
                setAliases: {},
                sets: {
                    fluent: {
                        label: "Fluent System Icons",
                        shortLabel: "Fluent",
                        source: payload.source || "microsoft/fluentui-system-icons",
                        icons,
                    },
                },
            };
        }

        return {
            defaultSet: "fluent",
            setAliases: {},
            sets: {
                fluent: {
                    label: "Fluent System Icons",
                    shortLabel: "Fluent",
                    source: "microsoft/fluentui-system-icons",
                    icons: [],
                },
            },
        };
    }

    addLegacySetShortLabels(sets) {
        const legacyShortLabels = {
            fluent: "Fluent",
            segoe: "Segoe",
        };

        return Object.fromEntries(
            Object.entries(sets).map(([key, set]) => {
                if (!set || typeof set !== "object" || set.shortLabel || !legacyShortLabels[key]) {
                    return [key, set];
                }
                return [key, { ...set, shortLabel: legacyShortLabels[key] }];
            })
        );
    }

    normalizeSetAliases(aliases) {
        if (!aliases || typeof aliases !== "object" || Array.isArray(aliases)) {
            return {};
        }

        return Object.fromEntries(
            Object.entries(aliases).filter(
                ([alias, target]) => typeof alias === "string" && typeof target === "string"
            )
        );
    }

    resolveSetKey(requestedKey) {
        if (!requestedKey) {
            return null;
        }
        if (this.iconSets[requestedKey]) {
            return requestedKey;
        }

        const aliasTarget = this.setAliases[requestedKey];
        return aliasTarget && this.iconSets[aliasTarget] ? aliasTarget : null;
    }

    async loadIcons() {
        try {
            const response = await fetch("./icon-data.json");
            if (!response.ok) {
                throw new Error(`Failed to fetch icon data: ${response.status}`);
            }

            const payload = await response.json();
            const normalized = this.normalizePayload(payload);
            this.iconSets = normalized.sets;
            this.setAliases = normalized.setAliases;
            void warmIconCache(payload);

            const availableSetKeys = Object.keys(this.iconSets);
            const preferredSet = normalized.defaultSet;
            this.currentSetKey = availableSetKeys.includes(preferredSet)
                ? preferredSet
                : availableSetKeys[0] || "fluent";
            this.renderSetPicker();
        } catch (error) {
            console.error("Error loading icons:", error);
            this.showError("Failed to load icons. Please make sure icon-data.json exists.");
        }
    }

    setupEventListeners() {
        const searchInput = document.getElementById("searchInput");
        const searchClearButton = document.getElementById("searchClearButton");
        const modalTitle = document.getElementById("modalTitle");
        const panelMeta = document.querySelector(".panel-meta");
        const panel = document.getElementById("iconModal");
        const panelContent = panel?.querySelector(".modal-content");
        const panelSizeButton = document.getElementById("panelSizeButton");
        const panelSizeMenu = document.getElementById("panelSizeMenu");

        searchInput.addEventListener("input", (event) => {
            const nextValue = event.target.value;
            this.updateSearchClearButton();
            if (this.searchDebounceTimer) {
                clearTimeout(this.searchDebounceTimer);
            }
            this.searchDebounceTimer = setTimeout(() => {
                this.filterIcons(nextValue);
            }, this.searchDebounceMs);
        });

        searchClearButton.addEventListener("click", () => {
            if (this.searchDebounceTimer) {
                clearTimeout(this.searchDebounceTimer);
                this.searchDebounceTimer = null;
            }

            searchInput.value = "";
            this.updateSearchClearButton();
            this.filterIcons("");
            searchInput.focus();
        });

        this.updateSearchClearButton();

        document.querySelectorAll(".style-mode-button").forEach((button) => {
            button.addEventListener("click", () => {
                const mode = button.dataset.styleMode;
                const previousMode = this.styleMode;
                if ((mode || "") === previousMode) {
                    this.setStyleMode("");
                } else {
                    this.setStyleMode(mode || "");
                }
                if (this.styleMode !== previousMode) {
                    this.applyStyleModeToRenderedCards();
                    this.updateStats();
                }
            });
        });

        document.getElementById("iconSetSelect")?.addEventListener("change", (event) => {
            this.switchSet(event.currentTarget.value);
        });

        document.querySelectorAll(".panel-variant-tab").forEach((button) => {
            button.addEventListener("click", () => {
                const variant = button.dataset.variant;
                if (!variant) {
                    return;
                }
                this.setActivePanelVariant(variant);
            });
        });

        if (panelSizeButton) {
            panelSizeButton.addEventListener("click", () => {
                this.togglePanelSizeMenu();
            });

            panelSizeButton.addEventListener("keydown", (event) => {
                if (event.key === "ArrowDown" || event.key === "ArrowUp") {
                    event.preventDefault();
                    this.openPanelSizeMenu({
                        focusSelected: true,
                        focusLast: event.key === "ArrowUp",
                    });
                }
            });
        }

        if (panelSizeMenu) {
            panelSizeMenu.addEventListener("click", (event) => {
                const option = event.target.closest?.(".panel-size-option");
                if (!option) {
                    return;
                }
                this.selectPanelSize(Number(option.dataset.size));
            });

            panelSizeMenu.addEventListener("keydown", (event) => {
                this.handlePanelSizeMenuKeydown(event);
            });
        }

        const panelCurrentColorToggle = document.getElementById("panelCurrentColorToggle");
        if (panelCurrentColorToggle) {
            panelCurrentColorToggle.addEventListener("click", () => {
                this.toggleCurrentColorForActiveVariant();
            });
        }

        const panelCopyButton = document.getElementById("panelCopyBtn");
        if (panelCopyButton) {
            panelCopyButton.addEventListener("click", (event) => {
                if (!this.activePanelVariant) {
                    return;
                }
                copyToClipboard(event, this.activePanelVariant);
            });
        }

        const panelIncludeBoundsToggle = document.getElementById("panelIncludeBoundsToggle");
        if (panelIncludeBoundsToggle) {
            panelIncludeBoundsToggle.addEventListener("click", () => {
                this.includeBoundsEnabled = !this.includeBoundsEnabled;
                writeIncludeBoundsPreference(this.includeBoundsEnabled);
                this.syncIncludeBoundsToggle();
            });
            this.syncIncludeBoundsToggle();
        }

        const panelDownloadButton = document.getElementById("panelDownloadBtn");
        if (panelDownloadButton) {
            panelDownloadButton.addEventListener("click", () => {
                if (!this.activePanelVariant) {
                    return;
                }
                downloadIcon(this.activePanelVariant);
            });
        }

        if (modalTitle) {
            modalTitle.addEventListener("click", () => {
                this.openPanelMetaDetails();
            });
        }

        if (modalTitle) {
            modalTitle.addEventListener("pointerenter", (event) => {
                if (event.pointerType === "mouse") {
                    this.openPanelMetaDetails();
                }
            });

            modalTitle.addEventListener("pointerleave", (event) => {
                if (event.pointerType === "mouse") {
                    this.closePanelMetaDetails();
                }
            });
        }

        document.addEventListener("pointerdown", (event) => {
            const target = event.target instanceof Element ? event.target : null;

            if (
                panelSizeMenu &&
                !panelSizeMenu.hidden &&
                target &&
                !panelSizeMenu.contains(target) &&
                !panelSizeButton?.contains(target)
            ) {
                this.closePanelSizeMenu();
            }

            if (this.isPanelMetaDetailsOpen() && panelMeta && !panelMeta.contains(event.target)) {
                this.closePanelMetaDetails();
            }

            if (
                this.isIconPanelOpen() &&
                target &&
                !panel?.contains(target) &&
                !panelSizeMenu?.contains(target) &&
                !target.closest(".icon-card")
            ) {
                this.closeIconPanel();
            }
        });

        if (panelContent) {
            panelContent.addEventListener(
                "touchstart",
                (event) => {
                    this.resetPanelSwipeState();
                    if (event.touches.length !== 1) {
                        return;
                    }
                    const touch = event.touches[0];
                    const target = event.target instanceof Element ? event.target : null;
                    const verticalScroller = this.findPanelVerticalScroller(target, panelContent);
                    const horizontalScroller = target?.closest(".panel-toolbar") || null;
                    this.panelSwipeGesture = {
                        identifier: touch.identifier,
                        startX: touch.clientX,
                        startY: touch.clientY,
                        startTime: performance.now(),
                        axis: null,
                        dragOffset: 0,
                        verticalScroller,
                        horizontalScroller,
                        startScrollLeft: horizontalScroller?.scrollLeft || 0,
                    };
                },
                { passive: true }
            );

            panelContent.addEventListener(
                "touchmove",
                (event) => {
                    const gesture = this.panelSwipeGesture;
                    if (!gesture) {
                        return;
                    }
                    const touch = Array.from(event.touches).find(
                        (entry) => entry.identifier === gesture.identifier
                    );
                    if (!touch) {
                        return;
                    }

                    const deltaX = touch.clientX - gesture.startX;
                    const deltaY = touch.clientY - gesture.startY;
                    const absoluteX = Math.abs(deltaX);
                    const absoluteY = Math.abs(deltaY);

                    if (gesture.verticalScroller) {
                        return;
                    }

                    event.preventDefault();

                    if (!gesture.axis && Math.max(absoluteX, absoluteY) >= 4) {
                        gesture.axis = absoluteY > absoluteX ? "vertical" : "horizontal";
                    }

                    if (gesture.axis === "horizontal") {
                        if (gesture.horizontalScroller) {
                            gesture.horizontalScroller.scrollLeft = gesture.startScrollLeft - deltaX;
                            this.syncToolbarScrollIndicators();
                        }
                        return;
                    }

                    if (gesture.axis !== "vertical") {
                        return;
                    }

                    gesture.dragOffset = Math.max(0, deltaY);
                    panel.classList.add("is-swipe-dragging");
                    panel.style.setProperty("--panel-swipe-offset", `${gesture.dragOffset}px`);
                },
                { passive: false }
            );

            panelContent.addEventListener(
                "touchend",
                (event) => {
                    const gesture = this.panelSwipeGesture;
                    if (!gesture) {
                        return;
                    }
                    const touch = Array.from(event.changedTouches).find(
                        (entry) => entry.identifier === gesture.identifier
                    );
                    if (!touch) {
                        this.resetPanelSwipeState();
                        return;
                    }
                    const deltaX = touch.clientX - gesture.startX;
                    const deltaY = touch.clientY - gesture.startY;
                    const elapsed = Math.max(1, performance.now() - gesture.startTime);
                    const velocityY = deltaY / elapsed;
                    const isDownwardSwipe =
                        gesture.axis === "vertical" &&
                        deltaY > Math.abs(deltaX) * 1.1 &&
                        (deltaY >= 72 || (deltaY >= 24 && velocityY >= 0.5));

                    this.panelSwipeGesture = null;
                    if (isDownwardSwipe) {
                        this.dismissPanelFromSwipe();
                    } else {
                        this.settlePanelSwipe();
                    }
                },
                { passive: true }
            );

            panelContent.addEventListener(
                "touchcancel",
                () => {
                    this.panelSwipeGesture = null;
                    this.settlePanelSwipe();
                },
                { passive: true }
            );
        }

        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                if (this.closePanelSizeMenu({ restoreFocus: true })) {
                    return;
                }
                if (this.closePanelMetaDetails()) {
                    return;
                }
                this.closeIconPanel();
            }
        });

        window.addEventListener("resize", () => {
            this.closePanelSizeMenu();
            this.syncPanelActionPlacement();
            this.syncPanelMetaDetails();
            this.syncToolbarScrollIndicators();
        });
        this.setupToolbarScrollIndicators();
    }

    setupFooterOffset() {
        const footer = document.querySelector(".site-footer");
        if (!footer) {
            return;
        }

        const syncFooterOffset = () => {
            const footerHeight = Math.ceil(footer.getBoundingClientRect().height);
            document.documentElement.style.setProperty("--site-footer-height", `${footerHeight}px`);
        };

        syncFooterOffset();

        if (typeof ResizeObserver !== "undefined") {
            this.footerResizeObserver = new ResizeObserver(syncFooterOffset);
            this.footerResizeObserver.observe(footer);
        }
    }

    setupToolbarScrollIndicators() {
        this.toolbarScrollIndicators = Array.from(
            document.querySelectorAll(".top-controls, .panel-toolbar")
        );

        this.toolbarScrollIndicators.forEach((toolbar) => {
            toolbar.addEventListener(
                "scroll",
                () => {
                    this.closePanelSizeMenu();
                    this.syncToolbarScrollIndicators();
                },
                { passive: true }
            );
        });

        if (typeof ResizeObserver !== "undefined") {
            this.toolbarScrollObserver = new ResizeObserver(() => {
                this.syncPanelActionPlacement();
                this.syncToolbarScrollIndicators();
            });
            this.toolbarScrollIndicators.forEach((toolbar) => {
                this.toolbarScrollObserver.observe(toolbar);
            });
        }

        this.syncPanelActionPlacement();
        this.syncToolbarScrollIndicators();
    }

    setPanelActionsPromoted(promoted) {
        const panel = document.getElementById("iconModal");
        const panelMeta = panel?.querySelector(".panel-meta");
        const actions = document.getElementById("panelActionsGroup");
        const anchor = document.getElementById("panelActionsAnchor");
        if (!panel || !panelMeta || !actions || !anchor) {
            return;
        }

        panel.classList.toggle("has-promoted-actions", promoted);
        if (promoted) {
            if (actions.parentElement !== panelMeta) {
                panelMeta.appendChild(actions);
            }
        } else if (actions.previousElementSibling !== anchor) {
            anchor.insertAdjacentElement("afterend", actions);
        }
    }

    syncPanelActionPlacement() {
        const panel = document.getElementById("iconModal");
        const toolbar = panel?.querySelector(".panel-toolbar");
        if (!panel || !toolbar) {
            return;
        }

        this.setPanelActionsPromoted(false);
        const shouldMeasure = this.isIconPanelOpen() && this.isCompactPanelLayout();
        const shouldPromote = shouldMeasure && toolbar.scrollWidth - toolbar.clientWidth > 1;
        this.setPanelActionsPromoted(shouldPromote);

        if (shouldPromote) {
            toolbar.scrollLeft = 0;
        }
        this.syncPanelTitleState();
    }

    syncToolbarScrollIndicators() {
        (this.toolbarScrollIndicators || []).forEach((toolbar) => {
            const maximumScrollLeft = Math.max(0, toolbar.scrollWidth - toolbar.clientWidth);
            const canScroll = maximumScrollLeft > 1;

            toolbar.classList.toggle("has-overflow-left", canScroll && toolbar.scrollLeft > 1);
            toolbar.classList.toggle(
                "has-overflow-right",
                canScroll && toolbar.scrollLeft < maximumScrollLeft - 1
            );
        });
    }

    isCompactPanelLayout() {
        return window.matchMedia("(max-width: 600px)").matches;
    }

    findPanelVerticalScroller(target, panelContent) {
        let current = target;
        while (current && current !== panelContent) {
            const style = getComputedStyle(current);
            const canScrollVertically =
                /(auto|scroll)/.test(style.overflowY) &&
                current.scrollHeight > current.clientHeight + 1;
            if (canScrollVertically) {
                return current;
            }
            current = current.parentElement;
        }
        return null;
    }

    resetPanelSwipeState() {
        const panel = document.getElementById("iconModal");
        if (this.panelSwipeAnimationTimer) {
            clearTimeout(this.panelSwipeAnimationTimer);
            this.panelSwipeAnimationTimer = null;
        }
        this.panelSwipeGesture = null;
        panel?.classList.remove(
            "is-swipe-dragging",
            "is-swipe-settling",
            "is-swipe-dismissing"
        );
        panel?.style.removeProperty("--panel-swipe-offset");
    }

    settlePanelSwipe() {
        const panel = document.getElementById("iconModal");
        if (!panel) {
            return;
        }
        panel.classList.remove("is-swipe-dragging", "is-swipe-dismissing");
        panel.classList.add("is-swipe-settling");
        panel.style.setProperty("--panel-swipe-offset", "0px");
        this.panelSwipeAnimationTimer = setTimeout(() => {
            this.resetPanelSwipeState();
        }, 180);
    }

    dismissPanelFromSwipe() {
        const panel = document.getElementById("iconModal");
        if (!panel) {
            return;
        }
        const panelBounds = panel.getBoundingClientRect();
        const exitDistance = Math.max(panelBounds.height, window.innerHeight - panelBounds.top + 24);
        panel.classList.remove("is-swipe-dragging", "is-swipe-settling");
        panel.classList.add("is-swipe-dismissing");
        panel.style.setProperty("--panel-swipe-offset", `${exitDistance}px`);
        this.panelSwipeAnimationTimer = setTimeout(() => {
            this.closeIconPanel();
        }, 180);
    }

    isPanelMetaDetailsOpen() {
        const details = document.getElementById("panelMetaDetails");
        return this.isCompactPanelLayout() && Boolean(details && !details.hidden);
    }

    syncPanelTitleState() {
        const panel = document.getElementById("iconModal");
        const title = document.getElementById("modalTitle");
        const fullTitle = document.getElementById("modalFullTitle");
        const description = document.getElementById("modalDescription");
        const metaphors = document.getElementById("metaphorsList");
        if (!panel || !title || !fullTitle || !description || !metaphors) {
            return;
        }

        const isPromoted = panel.classList.contains("has-promoted-actions");
        const isTruncated =
            isPromoted && title.clientWidth > 0 && title.scrollWidth - title.clientWidth > 1;
        const hasDescription = Boolean(description.textContent.trim());
        const hasMetaphors = Boolean(metaphors.children.length);
        const hasDetails = isTruncated || hasDescription || hasMetaphors;

        fullTitle.textContent = title.textContent;
        fullTitle.hidden = !isTruncated;
        title.disabled = !hasDetails;
        title.classList.toggle("has-meta-details", hasDetails);
        title.setAttribute("aria-expanded", "false");
    }

    syncPanelMetaDetails() {
        const details = document.getElementById("panelMetaDetails");
        const title = document.getElementById("modalTitle");
        if (!details || !title) {
            return;
        }

        if (title.disabled) {
            details.hidden = true;
            title.setAttribute("aria-expanded", "false");
            return;
        }

        details.hidden = this.isCompactPanelLayout();
        title.setAttribute("aria-expanded", "false");
    }

    openPanelMetaDetails() {
        if (!this.isCompactPanelLayout()) {
            return;
        }

        const details = document.getElementById("panelMetaDetails");
        const title = document.getElementById("modalTitle");
        if (!details || !title || title.disabled) {
            return;
        }

        details.hidden = false;
        title.setAttribute("aria-expanded", "true");
    }

    closePanelMetaDetails() {
        const details = document.getElementById("panelMetaDetails");
        const title = document.getElementById("modalTitle");
        if (!this.isPanelMetaDetailsOpen() || !details || !title) {
            return false;
        }

        details.hidden = true;
        title.setAttribute("aria-expanded", "false");
        return true;
    }

    isPanelSizeMenuOpen() {
        const menu = document.getElementById("panelSizeMenu");
        return Boolean(menu?.classList.contains("is-open"));
    }

    positionPanelSizeMenu() {
        const button = document.getElementById("panelSizeButton");
        const menu = document.getElementById("panelSizeMenu");
        if (!button || !menu || menu.hidden) {
            return;
        }

        const rect = button.getBoundingClientRect();
        menu.style.left = `${Math.round(rect.left)}px`;
        menu.style.top = `${Math.round(rect.bottom)}px`;
        menu.style.width = `${Math.round(rect.width)}px`;
    }

    openPanelSizeMenu(options = {}) {
        const { focusSelected = false, focusLast = false } = options;
        const button = document.getElementById("panelSizeButton");
        const menu = document.getElementById("panelSizeMenu");
        const wrap = document.getElementById("panelSizeWrap");
        if (!button || !menu || button.disabled || !menu.children.length) {
            return;
        }

        if (this.panelSizeMenuCloseTimer) {
            clearTimeout(this.panelSizeMenuCloseTimer);
            this.panelSizeMenuCloseTimer = null;
        }

        menu.hidden = false;
        this.positionPanelSizeMenu();
        void menu.offsetHeight;
        menu.classList.add("is-open");
        button.setAttribute("aria-expanded", "true");
        wrap?.classList.add("is-open");

        if (focusSelected) {
            const selected = menu.querySelector('[aria-selected="true"]');
            const fallback = focusLast ? menu.lastElementChild : menu.firstElementChild;
            (selected || fallback)?.focus();
        }
    }

    closePanelSizeMenu(options = {}) {
        const { restoreFocus = false, immediate = false } = options;
        const button = document.getElementById("panelSizeButton");
        const menu = document.getElementById("panelSizeMenu");
        const wrap = document.getElementById("panelSizeWrap");
        if (!menu) {
            return false;
        }

        const wasOpen = menu.classList.contains("is-open");
        const wasVisible = !menu.hidden;
        menu.classList.remove("is-open");
        button?.setAttribute("aria-expanded", "false");
        wrap?.classList.remove("is-open");
        if (restoreFocus && wasOpen) {
            button?.focus();
        }

        if (this.panelSizeMenuCloseTimer) {
            clearTimeout(this.panelSizeMenuCloseTimer);
            this.panelSizeMenuCloseTimer = null;
        }

        const finishClose = () => {
            if (!menu.classList.contains("is-open")) {
                menu.hidden = true;
            }
            this.panelSizeMenuCloseTimer = null;
        };

        const prefersReducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
        if (!wasVisible || immediate || prefersReducedMotion) {
            finishClose();
        } else {
            this.panelSizeMenuCloseTimer = setTimeout(finishClose, PANEL_SIZE_MENU_HIDE_DELAY_MS);
        }
        return wasOpen;
    }

    togglePanelSizeMenu() {
        if (this.isPanelSizeMenuOpen()) {
            this.closePanelSizeMenu();
        } else {
            this.openPanelSizeMenu();
        }
    }

    handlePanelSizeMenuKeydown(event) {
        const menu = document.getElementById("panelSizeMenu");
        if (!menu) {
            return;
        }

        const options = Array.from(menu.querySelectorAll(".panel-size-option"));
        const activeIndex = options.indexOf(document.activeElement);
        let nextIndex = null;

        if (event.key === "ArrowDown") {
            nextIndex = activeIndex < 0 ? 0 : (activeIndex + 1) % options.length;
        } else if (event.key === "ArrowUp") {
            nextIndex = activeIndex < 0 ? options.length - 1 : (activeIndex - 1 + options.length) % options.length;
        } else if (event.key === "Home") {
            nextIndex = 0;
        } else if (event.key === "End") {
            nextIndex = options.length - 1;
        } else if (event.key === "Escape") {
            event.preventDefault();
            event.stopPropagation();
            this.closePanelSizeMenu({ restoreFocus: true });
            return;
        }

        if (nextIndex !== null && options[nextIndex]) {
            event.preventDefault();
            options[nextIndex].focus();
        }
    }

    selectPanelSize(size) {
        if (!this.activePanelVariant || !Number.isFinite(size)) {
            return;
        }

        this.panelSelectedSizes[this.activePanelVariant] = size;
        const sizeValue = document.getElementById("panelSizeValue");
        const menu = document.getElementById("panelSizeMenu");
        if (sizeValue) {
            sizeValue.textContent = String(size);
        }
        menu?.querySelectorAll(".panel-size-option").forEach((option) => {
            option.setAttribute("aria-selected", String(Number(option.dataset.size) === size));
        });
        this.updateModalVariantPreview(this.activePanelVariant);
        this.closePanelSizeMenu({ restoreFocus: true });
    }

    openIconPanel() {
        const panel = document.getElementById("iconModal");
        if (!panel) {
            return;
        }

        panel.classList.add("is-open");
        panel.setAttribute("aria-hidden", "false");
        document.body.classList.add("icon-panel-open");
        requestAnimationFrame(() => {
            this.syncPanelActionPlacement();
            this.syncPanelMetaDetails();
            this.syncToolbarScrollIndicators();
        });
    }

    isIconPanelOpen() {
        const panel = document.getElementById("iconModal");
        return Boolean(panel?.classList.contains("is-open"));
    }

    setSelectedIcon(iconName) {
        const previousName = this.selectedIconName;
        if (previousName) {
            const previousCard = this.cardByName.get(previousName);
            previousCard?.classList.remove("is-selected");
        }

        this.selectedIconName = iconName || null;
        if (this.selectedIconName) {
            const nextCard = this.cardByName.get(this.selectedIconName);
            nextCard?.classList.add("is-selected");
        }
    }

    clearSelectedIcon() {
        this.setSelectedIcon(null);
    }

    closeIconPanel(options = {}) {
        const { clearSelection = true } = options;
        const panel = document.getElementById("iconModal");
        if (!panel) {
            return;
        }

        this.resetPanelSwipeState();
        panel.classList.remove("is-open");
        panel.setAttribute("aria-hidden", "true");
        document.body.classList.remove("icon-panel-open");
        this.setPanelActionsPromoted(false);
        this.closePanelSizeMenu({ immediate: true });
        this.closePanelMetaDetails();
        this.currentIcon = null;
        if (clearSelection) {
            this.clearSelectedIcon();
        }
        this.updateUrlForSelection(null);
    }

    switchSet(setKey) {
        if (!setKey || !this.iconSets[setKey] || setKey === this.currentSetKey) {
            return;
        }

        this.currentSetKey = setKey;
        this.closeIconPanel();
        this.applyCurrentSet();
    }

    renderSetPicker() {
        const picker = document.getElementById("iconSetSelect");
        if (!picker) {
            return;
        }

        const fragment = document.createDocumentFragment();
        Object.entries(this.iconSets).forEach(([key, set]) => {
            const option = document.createElement("option");
            const optionLabel = getCollectionPickerOption(set, key);

            option.value = key;
            option.textContent = optionLabel.text;
            option.title = optionLabel.title;
            fragment.appendChild(option);
        });
        picker.replaceChildren(fragment);
    }

    applyCurrentSet() {
        const fallbackSet = Object.keys(this.iconSets)[0];
        if (!this.iconSets[this.currentSetKey] && fallbackSet) {
            this.currentSetKey = fallbackSet;
        }

        this.currentSet = this.iconSets[this.currentSetKey] || {
            label: "Icons",
            source: "",
            icons: [],
        };

        this.icons = Array.isArray(this.currentSet.icons) ? this.currentSet.icons : [];
        this.prepareSearchIndex();
        this.filteredIcons = [...this.icons];
        this.selectedIconName = null;
        this.activePanelVariant = null;
        this.cardByName = new Map();
        this.renderedAllCards = false;
        this.lastAppliedStyleMode = null;
        this.syncSetPicker();
        this.syncStyleModeControlsForSet();
        this.updateSetSubtitle();

        const searchTerm = document.getElementById("searchInput")?.value || "";
        this.filterIcons(searchTerm);
    }

    // Deep link support: ?icon=<name>&set=<key> opens a specific icon (e.g. linked from the
    // PowerSpec Mdl2Icon enum docs). Switches to the set that holds the icon, filters the grid to it,
    // and opens its panel. Falls back to a plain search when the exact name isn't a distinct card
    // (some MDL2 variants are folded into a canonical family), so the link still lands usefully.
    applyDeepLink() {
        let params;
        try {
            params = new URLSearchParams(window.location.search);
        } catch (error) {
            return;
        }

        const iconParam = (params.get("icon") || "").trim();
        const setParam = (params.get("set") || "").trim();
        if (!iconParam && !setParam) {
            return;
        }

        let targetSetKey = this.resolveSetKey(setParam);
        if (!targetSetKey && iconParam) {
            for (const [key, set] of Object.entries(this.iconSets)) {
                const icons = Array.isArray(set.icons) ? set.icons : [];
                if (icons.some((entry) => entry.name === iconParam)) {
                    targetSetKey = key;
                    break;
                }
            }
        }

        // Preserve the incoming deep-link URL while we resolve it: switchSet/openModal would
        // otherwise rewrite (or clear) it mid-flight.
        this._applyingDeepLink = true;
        try {
            if (targetSetKey && targetSetKey !== this.currentSetKey) {
                this.switchSet(targetSetKey);
            }

            if (!iconParam) {
                return;
            }

            const exact = this.icons.find((entry) => entry.name === iconParam);
            const query = exact ? exact.displayName || iconParam : iconParam;
            const searchInput = document.getElementById("searchInput");
            if (searchInput) {
                searchInput.value = query;
                this.updateSearchClearButton();
            }
            this.filterIcons(query);

            if (exact) {
                this.openModal(exact.name);
                const card = this.cardByName.get(exact.name);
                card?.scrollIntoView({ block: "center", behavior: "smooth" });
            }
        } finally {
            this._applyingDeepLink = false;
        }
    }

    // Reflect the selected icon in the URL so any icon view is a copy-shareable deep link.
    updateUrlForSelection(iconName) {
        if (this._applyingDeepLink) {
            return;
        }
        try {
            const url = new URL(window.location.href);
            if (iconName) {
                url.searchParams.set("set", this.currentSetKey);
                url.searchParams.set("icon", iconName);
            } else {
                url.searchParams.delete("icon");
                url.searchParams.delete("set");
            }
            window.history.replaceState(null, "", url);
        } catch (error) {
            // Non-fatal: deep linking is a convenience, never block the UI on it.
        }
    }

    syncSetPicker() {
        const picker = document.getElementById("iconSetSelect");
        if (picker) {
            picker.value = this.currentSetKey;
        }
        this.syncToolbarScrollIndicators();
    }

    updateSetSubtitle() {
        const subtitle = document.getElementById("setSubtitle");
        if (!subtitle) {
            return;
        }

        const label = this.currentSet?.label || "Icons";
        const source = this.currentSet?.source || "";
        const sourceEntries = this.getCollectionSources(this.currentSet, source);
        subtitle.replaceChildren();

        const labelElement = document.createElement("span");
        labelElement.className = "set-subtitle-label";
        labelElement.textContent = label;
        subtitle.appendChild(labelElement);

        if (sourceEntries.length === 0) {
            return;
        }

        const sourceList = document.createElement("span");
        sourceList.className = "set-source-list";
        sourceList.setAttribute("aria-label", "Collection sources and licenses");

        sourceEntries.forEach((entry, index) => {
            if (index > 0) {
                sourceList.append(document.createTextNode(" · "));
            }

            this.appendCollectionReference(sourceList, entry.label, entry.url, "Collection source");
            if (entry.license) {
                sourceList.append(document.createTextNode(" ("));
                this.appendCollectionReference(sourceList, entry.license, entry.licenseUrl, "License");
                sourceList.append(document.createTextNode(")"));
            }
        });

        subtitle.append(sourceList);
    }

    getCollectionSources(collection, fallbackSource) {
        const entries = Array.isArray(collection?.sources) ? collection.sources : [];
        const normalized = entries.map((entry) => {
            if (typeof entry === "string") {
                return { label: entry.trim(), url: "", license: "", licenseUrl: "" };
            }

            if (!entry || typeof entry !== "object") {
                return null;
            }

            return {
                label: String(entry.label || entry.name || entry.reference || entry.url || "").trim(),
                url: this.getSafeExternalUrl(entry.url || entry.reference),
                license: String(entry.license || "").trim(),
                licenseUrl: this.getSafeExternalUrl(entry.licenseUrl),
            };
        }).filter((entry) => entry?.label);

        if (normalized.length === 0 && typeof fallbackSource === "string" && fallbackSource.trim()) {
            normalized.push({ label: fallbackSource.trim(), url: "", license: "", licenseUrl: "" });
        }

        return normalized;
    }

    getSafeExternalUrl(value) {
        if (typeof value !== "string" || !value.trim()) {
            return "";
        }

        try {
            const url = new URL(value);
            return ["http:", "https:"].includes(url.protocol) ? url.href : "";
        } catch (error) {
            return "";
        }
    }

    appendCollectionReference(container, label, url, accessibleType) {
        if (!url) {
            container.append(document.createTextNode(label));
            return;
        }

        const link = document.createElement("a");
        link.href = url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = label;
        link.setAttribute("aria-label", `${accessibleType}: ${label} (opens in a new tab)`);
        container.append(link);
    }

    getSetAvailableVariants() {
        const available = new Set();

        for (const icon of this.icons) {
            const variantKeys = Object.keys(icon.variants || {});
            variantKeys.forEach((variant) => available.add(variant));
        }

        return available;
    }

    setStyleMode(mode) {
        if (!["", "regular", "filled", "color"].includes(mode)) {
            return;
        }

        this.styleMode = mode;
        this.syncStyleModeButtons();
    }

    syncStyleModeButtons() {
        document.querySelectorAll(".style-mode-button").forEach((button) => {
            const isActive = button.dataset.styleMode === this.styleMode;
            button.classList.toggle("active", isActive);
            button.setAttribute("aria-selected", isActive ? "true" : "false");
        });
    }

    syncStyleModeControlsForSet() {
        const availableVariants = this.getSetAvailableVariants();
        const modeButtons = {
            regular: document.getElementById("filterModeRegular"),
            filled: document.getElementById("filterModeFilled"),
            color: document.getElementById("filterModeColor"),
        };

        const availability = {
            regular: availableVariants.has("regular"),
            filled: availableVariants.has("filled"),
            color: availableVariants.has("color"),
        };

        Object.entries(modeButtons).forEach(([mode, button]) => {
            if (!button) {
                return;
            }

            const isAvailable = availability[mode];
            button.disabled = !isAvailable;
            button.classList.toggle("disabled", !isAvailable);
        });

        if (this.styleMode && !availability[this.styleMode]) {
            this.styleMode = "";
        }

        this.syncStyleModeButtons();
    }

    getVariantData(icon, variant) {
        return icon?.variants?.[variant] || null;
    }

    shouldPreserveSourceColors(variant, variantData) {
        return variant === "color" || variantData?.preserveSourceColors === true;
    }

    hasVariant(icon, variant) {
        return Boolean(this.getVariantData(icon, variant));
    }

    isLegacyVariantData(variantData) {
        return typeof variantData === "string";
    }

    getSizeEntries(variantData) {
        if (!variantData || this.isLegacyVariantData(variantData)) {
            return {};
        }

        return variantData.sizes && typeof variantData.sizes === "object"
            ? variantData.sizes
            : {};
    }

    getVariantSizes(variantData) {
        if (!variantData || this.isLegacyVariantData(variantData)) {
            return [];
        }

        const sizes = Object.keys(this.getSizeEntries(variantData))
            .map((value) => Number(value))
            .filter((value) => Number.isFinite(value))
            .sort((a, b) => a - b);

        const fallbackDefault = Number(variantData.defaultSize);
        if (sizes.length === 0 && Number.isFinite(fallbackDefault)) {
            return [fallbackDefault];
        }

        return sizes;
    }

    getDefaultSize(variantData) {
        const sizes = this.getVariantSizes(variantData);
        if (sizes.length === 0) {
            return null;
        }

        const preferred = Number(variantData.defaultSize);
        if (Number.isFinite(preferred) && sizes.includes(preferred)) {
            return preferred;
        }

        return sizes[0];
    }

    normalizeSizeEntry(entry, variantData) {
        if (typeof entry === "string") {
            return {
                url: entry,
                svg: null,
                sourceUrl: entry,
            };
        }

        if (entry && typeof entry === "object") {
            const url = typeof entry.url === "string" ? entry.url : null;
            const svg = typeof entry.svg === "string" ? entry.svg : null;
            const remoteSource = entry.remoteSource && typeof entry.remoteSource === "object"
                ? entry.remoteSource
                : null;
            const sourceUrl =
                typeof entry.sourceUrl === "string"
                    ? entry.sourceUrl
                    : url ||
                      (typeof variantData?.sourceUrl === "string" ? variantData.sourceUrl : null);

            return { url, svg, sourceUrl, remoteSource };
        }

        return {
            url: null,
            svg: null,
            remoteSource: null,
            sourceUrl:
                typeof variantData?.sourceUrl === "string" ? variantData.sourceUrl : null,
        };
    }

    resolveVariantAsset(variantData, size) {
        if (!variantData) {
            return null;
        }

        if (this.isLegacyVariantData(variantData)) {
            return {
                size: null,
                url: null,
                svg: variantData,
                remoteSource: null,
                sourceUrl: null,
            };
        }

        const entries = this.getSizeEntries(variantData);
        const defaultSize = this.getDefaultSize(variantData);
        const resolvedSize =
            Number.isFinite(size) && entries[String(size)] ? Number(size) : defaultSize;

        if (resolvedSize && entries[String(resolvedSize)]) {
            return {
                size: resolvedSize,
                ...this.normalizeSizeEntry(entries[String(resolvedSize)], variantData),
            };
        }

        if (typeof variantData.previewSvg === "string" && variantData.previewSvg) {
            return {
                size: defaultSize,
                url: null,
                svg: variantData.previewSvg,
                remoteSource: null,
                sourceUrl:
                    typeof variantData.sourceUrl === "string" ? variantData.sourceUrl : null,
            };
        }

        if (typeof variantData.previewUrl === "string" && variantData.previewUrl) {
            return {
                size: defaultSize,
                url: variantData.previewUrl,
                svg: null,
                remoteSource: null,
                sourceUrl: variantData.previewUrl,
            };
        }

        const firstSizeKey = Object.keys(entries)[0];
        if (firstSizeKey) {
            return {
                size: Number(firstSizeKey),
                ...this.normalizeSizeEntry(entries[firstSizeKey], variantData),
            };
        }

        return {
            size: defaultSize,
            url: null,
            svg: null,
            remoteSource: null,
            sourceUrl:
                typeof variantData.sourceUrl === "string" ? variantData.sourceUrl : null,
        };
    }

    escapeHtmlAttribute(value) {
        return String(value)
            .replaceAll("&", "&amp;")
            .replaceAll('"', "&quot;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;");
    }

    normalizeSearchText(value) {
        return String(value || "")
            .toLowerCase()
            .replaceAll("_", " ")
            .replace(/\s+/g, " ")
            .trim();
    }

    matchesSearchValue(value, search, searchRaw) {
        const raw = String(value || "").toLowerCase();
        if (searchRaw && raw.includes(searchRaw)) {
            return true;
        }

        const normalized = this.normalizeSearchText(value);
        return search === "" || normalized.includes(search);
    }

    prepareSearchIndex() {
        this.iconByName = new Map();
        this.icons.forEach((icon) => {
            const aliases = Array.isArray(icon.aliases) ? icon.aliases : [];
            const metaphors = Array.isArray(icon.metaphors) ? icon.metaphors : [];
            const searchParts = [
                icon.name || "",
                icon.displayName || "",
                icon.description || "",
                ...aliases,
                ...metaphors,
            ]
                .filter(Boolean)
                .map((part) => String(part));

            const rawText = searchParts.join(" ").toLowerCase();
            icon._searchRaw = rawText;
            icon._searchNormalized = this.normalizeSearchText(rawText);
            icon._hasRegular = this.hasVariant(icon, "regular");
            icon._hasFilled = this.hasVariant(icon, "filled");
            icon._hasColor = this.hasVariant(icon, "color");
            icon._previewCache = {};
            this.iconByName.set(icon.name, icon);
        });
    }

    matchesStyleModeForIcon(icon, styleMode = this.getActiveStyleMode()) {
        return (
            !styleMode ||
            (styleMode === "regular" && Boolean(icon?._hasRegular)) ||
            (styleMode === "filled" && Boolean(icon?._hasFilled)) ||
            (styleMode === "color" && Boolean(icon?._hasColor))
        );
    }

    getPreviewVariantForMode(icon, styleMode = this.getActiveStyleMode()) {
        let previewOrder = ["regular", "filled", "color"];
        if (styleMode === "filled") {
            previewOrder = ["filled", "regular", "color"];
        } else if (styleMode === "color") {
            previewOrder = ["color", "regular", "filled"];
        }

        return previewOrder.find((variant) => this.hasVariant(icon, variant)) || null;
    }

    getCachedPreviewForMode(icon, styleMode = this.getActiveStyleMode()) {
        if (!icon) {
            return {
                variant: null,
                markup: '<div style="color: #ccc;">No preview</div>',
                colorClass: "",
            };
        }

        if (!icon._previewCache) {
            icon._previewCache = {};
        }

        if (icon._previewCache[styleMode]) {
            return icon._previewCache[styleMode];
        }

        const previewVariant = this.getPreviewVariantForMode(icon, styleMode);
        const variantData = previewVariant ? this.getVariantData(icon, previewVariant) : null;
        const asset = variantData
            ? this.resolveVariantAsset(variantData, this.getDefaultSize(variantData))
            : null;
        const previewMarkup = variantData
            ? this.renderPreviewMarkup(icon, previewVariant, variantData, asset)
            : '<div style="color: #ccc;">No preview</div>';
        const colorClass = this.shouldPreserveSourceColors(previewVariant, variantData)
            ? "has-color-variant"
            : "";

        const cached = {
            variant: previewVariant,
            asset,
            markup: previewMarkup,
            colorClass,
        };
        icon._previewCache[styleMode] = cached;
        return cached;
    }

    applyStyleToCard(card, icon, styleMode, isVisible, shouldRefreshPreview) {
        card.classList.toggle("is-hidden", !isVisible);
        if (!isVisible) {
            return;
        }

        if (!shouldRefreshPreview && card.dataset.previewMode === styleMode) {
            return;
        }

        const preview = this.getCachedPreviewForMode(icon, styleMode);
        const iconView = card.querySelector(".icon-view");
        if (!iconView) {
            return;
        }

        iconView.className = `icon-view ${preview.colorClass}`.trim();
        iconView.innerHTML = preview.markup;
        card.dataset.previewMode = styleMode;
        card.dataset.hasRemotePreview = preview.asset?.remoteSource ? "true" : "false";
        const nextRemotePreviewKey = preview.asset?.remoteSource
            ? this.remoteAssetKey(preview.asset)
            : "";
        if (nextRemotePreviewKey || card.dataset.remotePreviewKey !== nextRemotePreviewKey) {
            delete card.dataset.remotePreviewStatus;
            delete card.dataset.remotePreviewKey;
        }
    }

    toggleNoResultsMessage(isVisible) {
        const grid = document.getElementById("iconGrid");
        if (!grid) {
            return;
        }

        const noResults = grid.querySelector(".no-results");
        if (!noResults) {
            return;
        }

        noResults.style.display = isVisible ? "block" : "none";
    }

    applyStyleModeToRenderedCards() {
        if (!this.renderedAllCards || this.cardByName.size === 0) {
            return;
        }

        const styleMode = this.getActiveStyleMode();
        const searchMatches = new Set(this.filteredIcons.map((icon) => icon.name));
        const shouldRefreshVisiblePreviews = this.lastAppliedStyleMode !== styleMode;
        let visibleCount = 0;
        let selectedIconStillVisible = !this.selectedIconName;

        for (const icon of this.icons) {
            const card = this.cardByName.get(icon.name);
            if (!card) {
                continue;
            }

            const matchesSearch = searchMatches.has(icon.name);
            const matchesStyle = this.matchesStyleModeForIcon(icon, styleMode);
            const isVisible = matchesSearch && matchesStyle;
            const needsPreviewRefresh =
                (shouldRefreshVisiblePreviews && isVisible) ||
                (isVisible && card.dataset.previewMode !== styleMode);

            this.applyStyleToCard(card, icon, styleMode, isVisible, needsPreviewRefresh);
            if (isVisible) {
                visibleCount += 1;
            }

            if (this.selectedIconName && icon.name === this.selectedIconName && isVisible) {
                selectedIconStillVisible = true;
            }
        }

        if (!selectedIconStillVisible) {
            this.closeIconPanel();
        }

        this.lastAppliedStyleMode = styleMode;
        this.toggleNoResultsMessage(visibleCount === 0);
        this.syncRemotePreviewObservation();
    }

    renderPreviewMarkup(icon, variant, variantData, resolvedAsset = null) {
        const asset = resolvedAsset || this.resolveVariantAsset(variantData, this.getDefaultSize(variantData));
        if (!asset) {
            return '<div style="color: #ccc;">No preview</div>';
        }

        if (asset.svg) {
            return asset.svg;
        }

        if (asset.remoteSource) {
            const label = `${this.getIconDisplayName(icon)} ${variant}`;
            const escapedLabel = this.escapeHtmlAttribute(label);
            return `<span class="remote-icon-placeholder" role="img" aria-label="${escapedLabel} loading">...</span>`;
        }

        if (asset.url) {
            const label = `${this.getIconDisplayName(icon)} ${variant}`;
            const escapedLabel = this.escapeHtmlAttribute(label);
            if (variant !== "color") {
                const escapedUrl = this.escapeHtmlAttribute(asset.url);
                return `<span class="gallery-icon-mask" role="img" aria-label="${escapedLabel}" style="--gallery-icon-source: url('${escapedUrl}')"></span>`;
            }
            return `<img src="${asset.url}" alt="${escapedLabel}" loading="lazy" decoding="async">`;
        }

        return '<div style="color: #ccc;">No preview</div>';
    }

    filterIcons(searchTerm) {
        const searchRaw = String(searchTerm || "").toLowerCase().trim();
        const search = this.normalizeSearchText(searchRaw);
        const searchTerms = search.split(" ").filter(Boolean);

        this.filteredIcons = this.icons.filter((icon) => {
            const rawIndex = icon._searchRaw || "";
            const normalizedIndex = icon._searchNormalized || "";
            const searchMatch =
                searchTerms.length === 0 ||
                searchTerms.every((term) => rawIndex.includes(term) || normalizedIndex.includes(term));

            return searchMatch;
        });

        this.renderIcons();
        this.updateStats();
    }

    updateSearchClearButton() {
        const searchInput = document.getElementById("searchInput");
        const clearButton = document.getElementById("searchClearButton");
        const searchWrap = searchInput?.closest(".search-wrap");
        if (!searchInput || !clearButton || !searchWrap) {
            return;
        }

        const hasValue = searchInput.value.length > 0;
        clearButton.hidden = !hasValue;
        searchWrap.classList.toggle("has-search-value", hasValue);
    }

    renderIcons() {
        const grid = document.getElementById("iconGrid");
        if (!grid) {
            return;
        }

        if (!this.renderedAllCards) {
            if (this.icons.length === 0) {
                grid.innerHTML = '<div class="no-results">No icons available for this icon set.</div>';
                this.cardByName = new Map();
                this.renderedAllCards = true;
                this.lastAppliedStyleMode = this.getActiveStyleMode();
                return;
            }

            const allCardsMarkup = this.icons.map((icon) => this.renderIconCard(icon)).join("");
            grid.innerHTML = `${allCardsMarkup}<div class="no-results" style="display:none;">No icons found matching your criteria.</div>`;

            this.cardByName = new Map();
            grid.querySelectorAll(".icon-card").forEach((card) => {
                const iconName = card.dataset.iconName;
                if (iconName) {
                    this.cardByName.set(iconName, card);
                }
            });

            if (this.selectedIconName) {
                this.setSelectedIcon(this.selectedIconName);
            }

            this.renderedAllCards = true;
            this.lastAppliedStyleMode = null;
        }

        this.applyStyleModeToRenderedCards();
        this.syncRemotePreviewObservation();
    }

    renderIconCard(icon) {
        const styleMode = this.getActiveStyleMode();
        const preview = this.getCachedPreviewForMode(icon, styleMode);
        const escapedName = this.escapeHtmlAttribute(icon.name);
        const displayName = this.getIconDisplayName(icon);
        const escapedDisplayName = this.escapeHtmlAttribute(displayName);

        return `
            <div class="icon-card"
                data-icon-name="${escapedName}"
                data-preview-mode="${styleMode}"
                data-has-remote-preview="${preview.asset?.remoteSource ? "true" : "false"}"
                title="${escapedDisplayName}"
                aria-label="${escapedDisplayName}"
                onclick="iconBrowser.openModal('${icon.name}')">
                <div class="icon-view ${preview.colorClass}">
                    ${preview.markup}
                </div>
            </div>
        `;
    }

    setupRemotePreviewHydration() {
        if (!this.remoteIconSourceResolver) {
            console.error("Remote icon source support did not load; descriptor-backed icons are unavailable.");
            return;
        }

        if ("IntersectionObserver" in window) {
            this.remotePreviewObserver = new IntersectionObserver(
                (entries) => {
                    entries.forEach((entry) => {
                        if (!entry.isIntersecting) {
                            return;
                        }
                        this.remotePreviewObserver?.unobserve(entry.target);
                        const icon = this.iconByName.get(entry.target.dataset.iconName);
                        if (icon) {
                            void this.hydrateCardRemotePreview(entry.target, icon);
                        }
                    });
                },
                { rootMargin: "480px 0px" }
            );
            return;
        }

        const scheduleFallback = () => this.scheduleRemotePreviewFallback();
        window.addEventListener("scroll", scheduleFallback, { passive: true });
        window.addEventListener("resize", scheduleFallback);
    }

    syncRemotePreviewObservation() {
        if (!this.remoteIconSourceResolver) {
            return;
        }

        const cards = [...this.cardByName.values()].filter(
            (card) =>
                card.dataset.hasRemotePreview === "true" &&
                !card.classList.contains("is-hidden") &&
                card.dataset.remotePreviewStatus !== "complete" &&
                card.dataset.remotePreviewStatus !== "failed"
        );
        if (this.remotePreviewObserver) {
            this.remotePreviewObserver.disconnect();
            cards.forEach((card) => this.remotePreviewObserver.observe(card));
            return;
        }
        this.scheduleRemotePreviewFallback(cards);
    }

    scheduleRemotePreviewFallback(cards = null) {
        if (this.remotePreviewFallbackScheduled) {
            return;
        }
        this.remotePreviewFallbackScheduled = true;
        requestAnimationFrame(() => {
            this.remotePreviewFallbackScheduled = false;
            const candidates = cards || [...this.cardByName.values()].filter(
                (card) =>
                    card.dataset.hasRemotePreview === "true" &&
                    !card.classList.contains("is-hidden") &&
                    card.dataset.remotePreviewStatus !== "complete" &&
                    card.dataset.remotePreviewStatus !== "failed"
            );
            const viewportBottom = window.innerHeight + 480;
            candidates
                .filter((card) => {
                    const bounds = card.getBoundingClientRect();
                    return bounds.bottom >= -480 && bounds.top <= viewportBottom;
                })
                .slice(0, 24)
                .forEach((card) => {
                    const icon = this.iconByName.get(card.dataset.iconName);
                    if (icon) {
                        void this.hydrateCardRemotePreview(card, icon);
                    }
                });
        });
    }

    remoteAssetKey(asset) {
        const source = asset?.remoteSource;
        return source
            ? [source.url, source.format, source.selector, source.sha256 || ""].join("\n")
            : "";
    }

    async resolveAssetSvg(asset) {
        if (asset?.svg) {
            return asset.svg;
        }
        if (asset?.remoteSource) {
            if (!this.remoteIconSourceResolver) {
                throw new Error("Remote icon source support did not load");
            }
            return this.remoteIconSourceResolver.resolve(asset.remoteSource);
        }
        if (asset?.url) {
            return fetchSvgText(asset.url);
        }
        throw new Error("The selected icon has no SVG source");
    }

    async hydrateCardRemotePreview(card, icon) {
        const preview = this.getCachedPreviewForMode(icon, card.dataset.previewMode || "");
        const asset = preview.asset;
        if (!asset?.remoteSource || card.classList.contains("is-hidden")) {
            return;
        }

        const key = this.remoteAssetKey(asset);
        if (
            card.dataset.remotePreviewKey === key &&
            (card.dataset.remotePreviewStatus === "loading" || card.dataset.remotePreviewStatus === "complete")
        ) {
            return;
        }

        const iconView = card.querySelector(".icon-view");
        if (!iconView) {
            return;
        }
        card.dataset.remotePreviewKey = key;
        card.dataset.remotePreviewStatus = "loading";
        try {
            const svg = await this.resolveAssetSvg(asset);
            if (card.dataset.remotePreviewKey !== key || card.classList.contains("is-hidden")) {
                return;
            }
            iconView.innerHTML = svg;
            card.dataset.remotePreviewStatus = "complete";
        } catch (error) {
            if (card.dataset.remotePreviewKey !== key) {
                return;
            }
            console.error(`Failed to hydrate remote preview for '${icon.name}' from ${asset.remoteSource.url}:`, error);
            iconView.innerHTML = '<span class="remote-icon-error" role="img" aria-label="Preview unavailable">!</span>';
            card.dataset.remotePreviewStatus = "failed";
        }
    }

    async hydrateDetailRemotePreview(iconDiv, asset, label) {
        const requestId = String(++this.remotePreviewRequestSequence);
        iconDiv.dataset.remotePreviewRequest = requestId;
        iconDiv.innerHTML = '<div class="remote-preview-status" role="status">Loading preview...</div>';
        try {
            const svg = await this.resolveAssetSvg(asset);
            if (iconDiv.dataset.remotePreviewRequest !== requestId) {
                return;
            }
            iconDiv.innerHTML = svg;
        } catch (error) {
            if (iconDiv.dataset.remotePreviewRequest !== requestId) {
                return;
            }
            console.error(`Failed to resolve remote preview for ${label} from ${asset.remoteSource.url}:`, error);
            iconDiv.innerHTML = '<div class="remote-preview-status" role="alert">Preview unavailable</div>';
        }
    }

    formatName(name) {
        return name
            .split("_")
            .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
            .join(" ");
    }

    getIconDisplayName(icon) {
        return icon?.displayName || this.formatName(icon?.name || "");
    }

    configureVariantControls(variant, variantData) {
        if (!variantData) {
            return;
        }

        if (this.isLegacyVariantData(variantData)) {
            this.panelSelectedSizes[variant] = null;
            return;
        }

        const sizes = this.getVariantSizes(variantData);
        const defaultSize = this.getDefaultSize(variantData);
        const selectedSize = this.panelSelectedSizes[variant];
        if (Number.isFinite(selectedSize) && sizes.includes(selectedSize)) {
            return;
        }

        this.panelSelectedSizes[variant] = defaultSize || sizes[0] || null;
    }

    shouldUseCurrentColor(variant) {
        if (variant === "color") {
            return false;
        }

        return Boolean(this.panelCurrentColorEnabled[variant]);
    }

    updateModalVariantPreview(variant) {
        if (!this.currentIcon) {
            return;
        }

        const variantData = this.getVariantData(this.currentIcon, variant);
        if (!variantData) {
            return;
        }

        const iconDiv = document.getElementById(`${variant}Icon`);
        if (!iconDiv) {
            return;
        }
        const colorClass = this.shouldPreserveSourceColors(variant, variantData)
            ? "has-color-variant"
            : "";

        iconDiv.className = `icon-view ${colorClass} icon-large`;

        const selectedSize = this.panelSelectedSizes[variant];
        const asset = this.resolveVariantAsset(variantData, selectedSize);

        if (!asset) {
            iconDiv.dataset.remotePreviewRequest = String(++this.remotePreviewRequestSequence);
            iconDiv.innerHTML = '<div style="color: #ccc;">No preview</div>';
            return;
        }

        if (asset.svg) {
            iconDiv.dataset.remotePreviewRequest = String(++this.remotePreviewRequestSequence);
            iconDiv.innerHTML = asset.svg;
        } else if (asset.remoteSource) {
            const label = `${this.getIconDisplayName(this.currentIcon)} ${variant}`;
            void this.hydrateDetailRemotePreview(iconDiv, asset, label);
        } else if (asset.url) {
            iconDiv.dataset.remotePreviewRequest = String(++this.remotePreviewRequestSequence);
            const label = `${this.getIconDisplayName(this.currentIcon)} ${variant}`;
            const escapedLabel = this.escapeHtmlAttribute(label);
            iconDiv.innerHTML = `<img src="${asset.url}" alt="${escapedLabel}" decoding="async">`;
        } else {
            iconDiv.dataset.remotePreviewRequest = String(++this.remotePreviewRequestSequence);
            iconDiv.innerHTML = '<div style="color: #ccc;">No preview</div>';
        }
    }

    openModal(iconName) {
        if (this.selectedIconName === iconName && this.isIconPanelOpen()) {
            this.closeIconPanel();
            return;
        }

        const icon = this.icons.find((entry) => entry.name === iconName);
        if (!icon) {
            return;
        }

        this.setSelectedIcon(iconName);
        this.currentIcon = icon;
        document.getElementById("modalTitle").textContent =
            this.getIconDisplayName(icon);
        const modalDescription = document.getElementById("modalDescription");
        const descriptionText =
            typeof icon.description === "string" ? icon.description.trim() : "";
        modalDescription.textContent = descriptionText;
        modalDescription.style.display = descriptionText ? "" : "none";

        const availableVariants = this.getAvailableVariantsForIcon(icon);
        availableVariants.forEach((variant) => {
            const variantData = this.getVariantData(icon, variant);
            this.configureVariantControls(variant, variantData);
        });

        const metaphorsList = document.getElementById("metaphorsList");
        if (icon.metaphors && icon.metaphors.length > 0) {
            metaphorsList.innerHTML = `
                <div class="metaphors-list">
                    ${icon.metaphors
                        .map((metaphor) => `<span class="metaphor-tag">${metaphor}</span>`)
                        .join("")}
                </div>
            `;
        } else {
            metaphorsList.innerHTML = "";
        }

        this.syncPanelTitleState();
        this.syncPanelMetaDetails();

        const preferredVariant = this.resolvePreferredPanelVariant(icon, availableVariants);
        this.setActivePanelVariant(preferredVariant, { availableVariants });
        this.openIconPanel();
        this.updateUrlForSelection(icon.name);
    }

    getAvailableVariantsForIcon(icon = this.currentIcon) {
        if (!icon) {
            return [];
        }

        return ["regular", "filled", "color"].filter((variant) => this.hasVariant(icon, variant));
    }

    resolvePreferredPanelVariant(icon, availableVariants = this.getAvailableVariantsForIcon(icon)) {
        if (availableVariants.length === 0) {
            return null;
        }

        if (this.activePanelVariant && availableVariants.includes(this.activePanelVariant)) {
            return this.activePanelVariant;
        }

        const mode = this.getActiveStyleMode();
        if (mode && availableVariants.includes(mode)) {
            return mode;
        }

        if (availableVariants.includes("regular")) {
            return "regular";
        }
        if (availableVariants.includes("filled")) {
            return "filled";
        }
        if (availableVariants.includes("color")) {
            return "color";
        }

        return availableVariants[0];
    }

    syncPanelVariantTabs(availableVariants = this.getAvailableVariantsForIcon()) {
        const buttons = Array.from(document.querySelectorAll(".panel-variant-tab"));
        const visibleButtons = [];

        buttons.forEach((button) => {
            const variant = button.dataset.variant;
            const isAvailable = Boolean(variant && availableVariants.includes(variant));
            const isActive = isAvailable && variant === this.activePanelVariant;

            button.style.display = isAvailable ? "inline-flex" : "none";
            button.disabled = false;
            button.classList.remove("disabled");
            button.classList.toggle("active", isActive);
            button.setAttribute("aria-selected", isActive ? "true" : "false");
            button.classList.remove("is-last-visible");

            if (isAvailable) {
                visibleButtons.push(button);
            }
        });

        const lastVisible = visibleButtons[visibleButtons.length - 1];
        if (lastVisible) {
            lastVisible.classList.add("is-last-visible");
        }
    }

    syncActiveVariantPanels() {
        ["regular", "filled", "color"].forEach((variant) => {
            const variantDiv = document.getElementById(`${variant}Variant`);
            if (!variantDiv) {
                return;
            }

            const isActive = variant === this.activePanelVariant;
            variantDiv.style.display = isActive ? "flex" : "none";
        });
    }

    setActivePanelVariant(variant, options = {}) {
        if (!this.currentIcon) {
            return;
        }

        const availableVariants = options.availableVariants || this.getAvailableVariantsForIcon();
        if (!availableVariants.length) {
            this.activePanelVariant = null;
            this.syncPanelVariantTabs([]);
            this.syncPanelToolbarControls([]);
            this.syncActiveVariantPanels();
            return;
        }

        this.activePanelVariant = availableVariants.includes(variant)
            ? variant
            : availableVariants[0];

        this.syncPanelVariantTabs(availableVariants);
        this.syncPanelToolbarControls(availableVariants);
        this.syncActiveVariantPanels();
        this.updateModalVariantPreview(this.activePanelVariant);
    }

    syncPanelToolbarControls(availableVariants = this.getAvailableVariantsForIcon()) {
        const sizeButton = document.getElementById("panelSizeButton");
        const sizeValue = document.getElementById("panelSizeValue");
        const sizeMenu = document.getElementById("panelSizeMenu");
        const sizeWrap = document.getElementById("panelSizeWrap");
        const currentColorToggle = document.getElementById("panelCurrentColorToggle");
        const copyButton = document.getElementById("panelCopyBtn");
        const downloadButton = document.getElementById("panelDownloadBtn");
        const hasActiveVariant = Boolean(
            this.activePanelVariant && availableVariants.includes(this.activePanelVariant)
        );

        if (copyButton) {
            copyButton.disabled = !hasActiveVariant;
        }
        if (downloadButton) {
            downloadButton.disabled = !hasActiveVariant;
        }

        if (!sizeButton || !sizeValue || !sizeMenu || !currentColorToggle) {
            return;
        }

        this.closePanelSizeMenu({ immediate: true });

        if (!hasActiveVariant) {
            sizeValue.textContent = "";
            sizeMenu.innerHTML = "";
            sizeButton.disabled = true;
            sizeButton.style.display = "none";
            sizeWrap?.classList.add("disabled");
            currentColorToggle.style.display = "inline-flex";
            currentColorToggle.disabled = true;
            currentColorToggle.classList.add("disabled");
            currentColorToggle.classList.remove("active");
            currentColorToggle.setAttribute("aria-pressed", "false");
            requestAnimationFrame(() => {
                this.syncPanelActionPlacement();
                this.syncToolbarScrollIndicators();
            });
            return;
        }

        const variant = this.activePanelVariant;
        const variantData = this.getVariantData(this.currentIcon, variant);
        const sizes = this.getVariantSizes(variantData);
        const fallbackSize = this.getDefaultSize(variantData) || sizes[0] || null;
        const selectedSize = this.panelSelectedSizes[variant];
        const resolvedSize =
            Number.isFinite(selectedSize) && sizes.includes(selectedSize)
                ? selectedSize
                : fallbackSize;

        this.panelSelectedSizes[variant] = resolvedSize;

        if (sizes.length > 0) {
            sizeValue.textContent = String(resolvedSize);
            sizeMenu.innerHTML = sizes
                .map(
                    (size) => `
                        <button type="button" class="panel-size-option" role="option" data-size="${size}" aria-selected="${size === resolvedSize}">${size}</button>
                    `
                )
                .join("");
            sizeButton.disabled = false;
            sizeWrap?.classList.remove("disabled");
        } else {
            sizeValue.textContent = "auto";
            sizeMenu.innerHTML = "";
            sizeButton.disabled = true;
            sizeWrap?.classList.add("disabled");
        }
        sizeButton.style.display = "inline-flex";

        if (variant === "color") {
            currentColorToggle.disabled = true;
            currentColorToggle.classList.add("disabled");
            currentColorToggle.classList.remove("active");
            currentColorToggle.setAttribute("aria-pressed", "false");
            currentColorToggle.style.display = "inline-flex";
        } else {
            const enabled = Boolean(this.panelCurrentColorEnabled[variant]);
            currentColorToggle.disabled = false;
            currentColorToggle.classList.remove("disabled");
            currentColorToggle.style.display = "inline-flex";
            currentColorToggle.classList.toggle("active", enabled);
            currentColorToggle.setAttribute("aria-pressed", enabled ? "true" : "false");
        }

        requestAnimationFrame(() => {
            this.syncPanelActionPlacement();
            this.syncToolbarScrollIndicators();
        });
    }

    toggleCurrentColorForActiveVariant() {
        const variant = this.activePanelVariant;
        if (!variant || variant === "color") {
            return;
        }

        this.panelCurrentColorEnabled[variant] = !this.panelCurrentColorEnabled[variant];
        this.syncPanelToolbarControls();
    }

    syncIncludeBoundsToggle() {
        const toggle = document.getElementById("panelIncludeBoundsToggle");
        if (!toggle) {
            return;
        }

        toggle.classList.toggle("active", this.includeBoundsEnabled);
        toggle.setAttribute("aria-pressed", this.includeBoundsEnabled ? "true" : "false");
    }

    getVariantSelection(variant) {
        if (!this.currentIcon) {
            return null;
        }

        const variantData = this.getVariantData(this.currentIcon, variant);
        if (!variantData) {
            return null;
        }

        const selectedSize = this.panelSelectedSizes[variant];
        const asset = this.resolveVariantAsset(variantData, selectedSize);
        if (!asset) {
            return null;
        }

        return {
            svgText: asset.svg,
            sourceUrl: asset.url,
            remoteSource: asset.remoteSource,
            asset,
            size: asset.size,
        };
    }

    updateStats() {
        const count = this.filteredIcons.filter((icon) =>
            this.matchesStyleModeForIcon(icon, this.getActiveStyleMode())
        ).length;
        const countElement = document.getElementById("iconCount");
        if (!countElement) {
            return;
        }

        const formattedCount = count.toLocaleString();
        const label = this.currentSet?.label || "icons";
        countElement.textContent = formattedCount;
        countElement.setAttribute("aria-label", `${formattedCount} visible icons in ${label}`);
        countElement.closest(".search-wrap")?.style.setProperty("--search-count-width", `${countElement.offsetWidth}px`);
    }

    showError(message) {
        const grid = document.getElementById("iconGrid");
        grid.innerHTML = `<div class="no-results">${message}</div>`;
        this.closeIconPanel();
        this.cardByName = new Map();
        this.renderedAllCards = false;
        this.lastAppliedStyleMode = null;
    }
}

const iconCacheVersionKey = "fluent-icons-icon-cache-version-v2";

function getIconCacheUrls(payload) {
    const urls = new Set();
    const visit = (value, isRemoteDescriptor = false) => {
        if (typeof value === "string") {
            if (!isRemoteDescriptor && /^https?:[^"\\]+\.svg(?:[?#][^"\\]*)?$/i.test(value)) {
                urls.add(value);
            }
            return;
        }
        if (Array.isArray(value)) {
            value.forEach((entry) => visit(entry, isRemoteDescriptor));
            return;
        }
        if (!value || typeof value !== "object") {
            return;
        }
        Object.entries(value).forEach(([key, entry]) => {
            visit(entry, isRemoteDescriptor || key === "remoteSource");
        });
    };

    visit(payload);
    return [...urls];
}

function updateCacheLoader(completed, total, failed = 0) {
    const loader = document.getElementById("cacheLoader");
    const progress = document.getElementById("cacheLoaderProgress");
    const label = document.getElementById("cacheLoaderLabel");
    if (!loader || !progress || !label) {
        return;
    }

    loader.hidden = false;
    progress.style.width = `${Math.round((completed / total) * 100)}%`;
    label.textContent = failed > 0
        ? `Caching icons: ${completed.toLocaleString()} / ${total.toLocaleString()} (${failed} retrying next launch)`
        : `Caching icons: ${completed.toLocaleString()} / ${total.toLocaleString()}`;
}

function hideCacheLoader() {
    const loader = document.getElementById("cacheLoader");
    if (loader) {
        loader.hidden = true;
    }
}

async function warmIconCache(payload) {
    const catalogVersion = payload.generatedAt;
    if (!catalogVersion || localStorage.getItem(iconCacheVersionKey) === catalogVersion) {
        return;
    }

    const urls = getIconCacheUrls(payload);
    if (urls.length === 0 || !("serviceWorker" in navigator)) {
        return;
    }

    const registration = await navigator.serviceWorker.ready;
    if (!registration.active) {
        return;
    }

    const channel = new MessageChannel();
    channel.port1.onmessage = ({ data }) => {
        if (data.type === "icon-cache-progress") {
            updateCacheLoader(data.completed, data.total, data.failed);
            return;
        }

        if (data.type === "icon-cache-complete") {
            updateCacheLoader(data.completed, data.total, data.failed);
            if (data.failed === 0) {
                localStorage.setItem(iconCacheVersionKey, catalogVersion);
                hideCacheLoader();
            }
        }
    };

    registration.active.postMessage({ type: "cache-icons", urls }, [channel.port2]);
}

const svgFetchCache = new Map();

async function fetchSvgText(url) {
    if (svgFetchCache.has(url)) {
        return svgFetchCache.get(url);
    }

    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(`Failed to fetch SVG from source (${response.status})`);
    }

    const svgText = await response.text();
    svgFetchCache.set(url, svgText);
    return svgText;
}

function setActionFeedback(button, success) {
    if (!button) {
        return;
    }

    button.classList.remove("is-success", "is-error");
    button.classList.add(success ? "is-success" : "is-error");
    window.setTimeout(() => {
        button.classList.remove("is-success", "is-error");
    }, 1200);
}

function formatSvgCoordinate(value) {
    const rounded = Number(value.toFixed(6));
    return Object.is(rounded, -0) ? "0" : String(rounded);
}

function withTransparentViewBoxBounds(svgText) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(svgText, "image/svg+xml");
    const root = doc.documentElement;
    const parserError = doc.querySelector("parsererror");

    if (parserError || !root || root.tagName.toLowerCase() !== "svg") {
        throw new Error("Cannot copy SVG: source markup is invalid");
    }

    const viewBox = root.getAttribute("viewBox")
        ?.trim()
        .split(/[\s,]+/)
        .map(Number);

    if (
        !viewBox ||
        viewBox.length !== 4 ||
        !viewBox.every(Number.isFinite) ||
        viewBox[2] <= 0 ||
        viewBox[3] <= 0
    ) {
        throw new Error("Cannot copy SVG: source has no valid viewBox");
    }

    const [minX, minY, width, height] = viewBox;
    const maxX = minX + width;
    const maxY = minY + height;
    const boundsPath = doc.createElementNS("http://www.w3.org/2000/svg", "path");

    boundsPath.setAttribute(
        "d",
        `M ${formatSvgCoordinate(minX)} ${formatSvgCoordinate(minY)} ` +
        `H ${formatSvgCoordinate(maxX)} V ${formatSvgCoordinate(maxY)} ` +
        `H ${formatSvgCoordinate(minX)} Z`
    );
    boundsPath.setAttribute("fill", "#000000");
    boundsPath.setAttribute("fill-opacity", "0");
    boundsPath.setAttribute("stroke", "none");
    boundsPath.setAttribute("data-viewbox-bounds", "true");

    const artworkGroup = doc.createElementNS("http://www.w3.org/2000/svg", "g");
    const rootLevelTags = new Set(["defs", "style", "title", "desc", "metadata"]);
    const originalNodes = [...root.childNodes];

    artworkGroup.setAttribute("data-viewbox-bounds-group", "true");
    artworkGroup.appendChild(boundsPath);

    for (const node of originalNodes) {
        const isRootLevelElement =
            node.nodeType === Node.ELEMENT_NODE &&
            rootLevelTags.has(node.tagName.toLowerCase());
        const isFormattingWhitespace =
            node.nodeType === Node.TEXT_NODE &&
            !node.textContent.trim();

        if (!isRootLevelElement && !isFormattingWhitespace) {
            artworkGroup.appendChild(node);
        }
    }

    root.appendChild(artworkGroup);

    return new XMLSerializer().serializeToString(root);
}

function toCurrentColorSvg(svgText) {
    try {
        const parser = new DOMParser();
        const doc = parser.parseFromString(svgText, "image/svg+xml");
        const root = doc.documentElement;

        if (!root || root.tagName.toLowerCase() !== "svg") {
            return svgText;
        }

        const elements = root.querySelectorAll("*");
        for (const element of elements) {
            const fill = element.getAttribute("fill");
            if (fill) {
                const normalized = fill.trim().toLowerCase();
                if (
                    normalized &&
                    normalized !== "none" &&
                    normalized !== "currentcolor" &&
                    !normalized.startsWith("url(")
                ) {
                    element.setAttribute("fill", "currentColor");
                }
            }

            const style = element.getAttribute("style");
            if (!style) {
                continue;
            }

            const declarations = style
                .split(";")
                .map((entry) => entry.trim())
                .filter(Boolean)
                .map((entry) => {
                    const separator = entry.indexOf(":");
                    if (separator === -1) {
                        return entry;
                    }

                    const key = entry.slice(0, separator).trim().toLowerCase();
                    const value = entry.slice(separator + 1).trim();
                    const normalized = value.toLowerCase();
                    if (
                        key === "fill" &&
                        normalized !== "none" &&
                        normalized !== "currentcolor" &&
                        !normalized.startsWith("url(")
                    ) {
                        return "fill:currentColor";
                    }

                    return `${key}:${value}`;
                });

            if (declarations.length > 0) {
                element.setAttribute("style", declarations.join(";"));
            }
        }

        return new XMLSerializer().serializeToString(root);
    } catch (error) {
        console.warn("Unable to transform SVG fill to currentColor:", error);
        return svgText;
    }
}

function prepareSvgOutput(originalSvg, variant) {
    const colorAdjustedSvg = iconBrowser.shouldUseCurrentColor(variant)
        ? toCurrentColorSvg(originalSvg)
        : originalSvg;

    return iconBrowser.includeBoundsEnabled
        ? withTransparentViewBoxBounds(colorAdjustedSvg)
        : colorAdjustedSvg;
}

async function copyToClipboard(clickEvent, variant) {
    const selection = iconBrowser.getVariantSelection(variant);
    if (!selection) {
        return;
    }

    const button = clickEvent?.currentTarget || clickEvent?.target;

    try {
        const originalSvg = await iconBrowser.resolveAssetSvg(selection.asset);
        const copiedSvg = prepareSvgOutput(originalSvg, variant);
        await navigator.clipboard.writeText(copiedSvg);
        setActionFeedback(button, true);
    } catch (error) {
        console.error("Failed to copy SVG:", error);
        setActionFeedback(button, false);
    }
}

async function downloadIcon(variant) {
    const selection = iconBrowser.getVariantSelection(variant);
    if (!selection) {
        return;
    }

    try {
        const originalSvg = await iconBrowser.resolveAssetSvg(selection.asset);
        const applyCurrentColor = iconBrowser.shouldUseCurrentColor(variant);
        const includeBounds = iconBrowser.includeBoundsEnabled;
        const finalSvg = prepareSvgOutput(originalSvg, variant);

        const blob = new Blob([finalSvg], { type: "image/svg+xml" });
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        const sizePart = selection.size ? `_${selection.size}` : "";
        const suffix = `${applyCurrentColor ? "_currentcolor" : ""}` +
            `${includeBounds ? "_bounds" : ""}`;

        anchor.href = url;
        anchor.download = `${iconBrowser.currentIcon.name}${sizePart}_${variant}${suffix}.svg`;
        document.body.appendChild(anchor);
        anchor.click();
        document.body.removeChild(anchor);
        URL.revokeObjectURL(url);
    } catch (error) {
        console.error("Failed to download SVG:", error);
    }
}

let iconBrowser;
if (typeof document !== "undefined") {
    document.addEventListener("DOMContentLoaded", () => {
        iconBrowser = new IconBrowser();
    });
}

if (typeof module !== "undefined" && module.exports) {
    module.exports = { getCollectionPickerOption };
}
