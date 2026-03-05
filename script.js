class IconBrowser {
    constructor() {
        this.iconSets = {};
        this.currentSetKey = "fluent";
        this.currentSet = null;
        this.styleMode = "all";
        this.icons = [];
        this.filteredIcons = [];
        this.currentIcon = null;
        this.renderJobId = 0;
        this.renderChunkSize = 180;
        this.styleApplyJobId = 0;
        this.iconByName = new Map();
        this.searchDebounceTimer = null;
        this.searchDebounceMs = 120;
        this.init();
    }

    getActiveStyleMode() {
        return this.styleMode;
    }

    async init() {
        await this.loadIcons();
        this.setupEventListeners();
        this.applyCurrentSet();
    }

    normalizePayload(payload) {
        if (Array.isArray(payload)) {
            return {
                defaultSet: "fluent",
                sets: {
                    fluent: {
                        label: "Fluent System Icons",
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
                    sets: payload.sets,
                };
            }

            const icons = Array.isArray(payload.icons) ? payload.icons : [];
            return {
                defaultSet: "fluent",
                sets: {
                    fluent: {
                        label: "Fluent System Icons",
                        source: payload.source || "microsoft/fluentui-system-icons",
                        icons,
                    },
                },
            };
        }

        return {
            defaultSet: "fluent",
            sets: {
                fluent: {
                    label: "Fluent System Icons",
                    source: "microsoft/fluentui-system-icons",
                    icons: [],
                },
            },
        };
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

            const availableSetKeys = Object.keys(this.iconSets);
            const preferredSet = normalized.defaultSet;
            this.currentSetKey = availableSetKeys.includes(preferredSet)
                ? preferredSet
                : availableSetKeys[0] || "fluent";
        } catch (error) {
            console.error("Error loading icons:", error);
            this.showError("Failed to load icons. Please make sure icon-data.json exists.");
        }
    }

    setupEventListeners() {
        const searchInput = document.getElementById("searchInput");
        const modal = document.getElementById("iconModal");
        const closeBtn = document.querySelector(".close");

        searchInput.addEventListener("input", (event) => {
            const nextValue = event.target.value;
            if (this.searchDebounceTimer) {
                clearTimeout(this.searchDebounceTimer);
            }
            this.searchDebounceTimer = setTimeout(() => {
                this.filterIcons(nextValue);
            }, this.searchDebounceMs);
        });

        document.querySelectorAll(".style-mode-button").forEach((button) => {
            button.addEventListener("click", () => {
                const mode = button.dataset.styleMode;
                const previousMode = this.styleMode;
                this.setStyleMode(mode || "all");
                if (this.styleMode !== previousMode) {
                    this.applyStyleModeToRenderedCards();
                    this.updateStats();
                }
            });
        });

        document.querySelectorAll(".set-tab").forEach((button) => {
            button.addEventListener("click", () => {
                const setKey = button.dataset.set;
                this.switchSet(setKey);
            });
        });

        ["regular", "filled", "color"].forEach((variant) => {
            const select = document.getElementById(`${variant}Size`);
            if (select) {
                select.addEventListener("change", () => {
                    this.updateModalVariantPreview(variant);
                });
            }
        });

        closeBtn.addEventListener("click", () => {
            modal.style.display = "none";
        });

        modal.addEventListener("click", (event) => {
            if (event.target === modal) {
                modal.style.display = "none";
            }
        });

        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                modal.style.display = "none";
            }
        });
    }

    switchSet(setKey) {
        if (!setKey || !this.iconSets[setKey] || setKey === this.currentSetKey) {
            return;
        }

        this.currentSetKey = setKey;
        this.currentIcon = null;
        document.getElementById("iconModal").style.display = "none";
        this.applyCurrentSet();
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
        this.syncSetTabs();
        this.syncStyleModeControlsForSet();
        this.updateSetSubtitle();

        const searchTerm = document.getElementById("searchInput")?.value || "";
        this.filterIcons(searchTerm);
    }

    syncSetTabs() {
        document.querySelectorAll(".set-tab").forEach((button) => {
            const setKey = button.dataset.set;
            const isAvailable = Boolean(this.iconSets[setKey]);
            const isActive = setKey === this.currentSetKey;

            button.style.display = isAvailable ? "inline-flex" : "none";
            button.classList.toggle("active", isActive);
            button.setAttribute("aria-selected", isActive ? "true" : "false");
        });
    }

    updateSetSubtitle() {
        const subtitle = document.getElementById("setSubtitle");
        if (!subtitle) {
            return;
        }

        const label = this.currentSet?.label || "Icons";
        const source = this.currentSet?.source || "";
        subtitle.textContent = source ? `${label} (${source})` : label;
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
        if (!["regular", "all", "filled"].includes(mode)) {
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
            all: document.getElementById("filterModeAll"),
            filled: document.getElementById("filterModeFilled"),
        };

        const availability = {
            regular: availableVariants.has("regular"),
            all: true,
            filled: availableVariants.has("filled"),
        };

        Object.entries(modeButtons).forEach(([mode, button]) => {
            if (!button) {
                return;
            }

            const isAvailable = availability[mode];
            button.disabled = !isAvailable;
            button.classList.toggle("disabled", !isAvailable);
        });

        if (!availability[this.styleMode]) {
            if (availability.all) {
                this.styleMode = "all";
            } else if (availability.regular) {
                this.styleMode = "regular";
            } else if (availability.filled) {
                this.styleMode = "filled";
            }
        }

        this.syncStyleModeButtons();
    }

    getVariantData(icon, variant) {
        return icon?.variants?.[variant] || null;
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
            const sourceUrl =
                typeof entry.sourceUrl === "string"
                    ? entry.sourceUrl
                    : url ||
                      (typeof variantData?.sourceUrl === "string" ? variantData.sourceUrl : null);

            return { url, svg, sourceUrl };
        }

        return {
            url: null,
            svg: null,
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
                sourceUrl:
                    typeof variantData.sourceUrl === "string" ? variantData.sourceUrl : null,
            };
        }

        if (typeof variantData.previewUrl === "string" && variantData.previewUrl) {
            return {
                size: defaultSize,
                url: variantData.previewUrl,
                svg: null,
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
            icon._previewCache = {};
            this.iconByName.set(icon.name, icon);
        });
    }

    matchesStyleModeForIcon(icon, styleMode = this.getActiveStyleMode()) {
        return (
            styleMode === "all" ||
            (styleMode === "regular" && Boolean(icon?._hasRegular)) ||
            (styleMode === "filled" && Boolean(icon?._hasFilled))
        );
    }

    getPreviewVariantForMode(icon, styleMode = this.getActiveStyleMode()) {
        let previewOrder = ["regular", "filled", "color"];
        if (styleMode === "filled") {
            previewOrder = ["filled", "regular", "color"];
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
        const previewMarkup = variantData
            ? this.renderPreviewMarkup(icon, previewVariant, variantData)
            : '<div style="color: #ccc;">No preview</div>';
        const colorClass = previewVariant === "color" ? "has-color-variant" : "";

        const cached = {
            variant: previewVariant,
            markup: previewMarkup,
            colorClass,
        };
        icon._previewCache[styleMode] = cached;
        return cached;
    }

    applyStyleToCard(card, styleMode) {
        const iconName = card?.dataset?.iconName;
        if (!iconName) {
            return;
        }

        const icon = this.iconByName.get(iconName);
        if (!icon) {
            return;
        }

        const isVisible = this.matchesStyleModeForIcon(icon, styleMode);
        card.style.display = isVisible ? "" : "none";
        if (!isVisible) {
            return;
        }

        if (card.dataset.previewMode === styleMode) {
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
    }

    applyStyleModeToRenderedCards() {
        const grid = document.getElementById("iconGrid");
        if (!grid) {
            return;
        }

        const cards = Array.from(grid.querySelectorAll(".icon-card"));
        if (cards.length === 0) {
            return;
        }

        const styleMode = this.getActiveStyleMode();
        const currentStyleJob = ++this.styleApplyJobId;
        const chunkSize = this.renderChunkSize;

        const applyChunk = (startIndex) => {
            if (currentStyleJob !== this.styleApplyJobId) {
                return;
            }

            const endIndex = Math.min(startIndex + chunkSize, cards.length);
            for (let index = startIndex; index < endIndex; index += 1) {
                this.applyStyleToCard(cards[index], styleMode);
            }

            if (endIndex < cards.length) {
                requestAnimationFrame(() => applyChunk(endIndex));
            }
        };

        applyChunk(0);
    }

    renderPreviewMarkup(icon, variant, variantData) {
        const asset = this.resolveVariantAsset(variantData, this.getDefaultSize(variantData));
        if (!asset) {
            return '<div style="color: #ccc;">No preview</div>';
        }

        if (asset.svg) {
            return asset.svg;
        }

        if (asset.url) {
            const label = `${this.formatName(icon.name)} ${variant}`;
            const escapedLabel = this.escapeHtmlAttribute(label);
            return `<img src="${asset.url}" alt="${escapedLabel}" loading="lazy" decoding="async">`;
        }

        return '<div style="color: #ccc;">No preview</div>';
    }

    filterIcons(searchTerm) {
        const searchRaw = String(searchTerm || "").toLowerCase().trim();
        const search = this.normalizeSearchText(searchRaw);

        this.filteredIcons = this.icons.filter((icon) => {
            const rawIndex = icon._searchRaw || "";
            const normalizedIndex = icon._searchNormalized || "";
            const searchMatch =
                search === "" ||
                (searchRaw && rawIndex.includes(searchRaw)) ||
                normalizedIndex.includes(search);

            return searchMatch;
        });

        this.renderIcons();
        this.updateStats();
    }

    renderIcons() {
        const grid = document.getElementById("iconGrid");
        const currentRenderJob = ++this.renderJobId;
        this.styleApplyJobId += 1;

        if (this.filteredIcons.length === 0) {
            grid.innerHTML = '<div class="no-results">No icons found matching your criteria.</div>';
            return;
        }

        grid.innerHTML = "";
        const totalIcons = this.filteredIcons.length;

        const appendChunk = (startIndex) => {
            if (currentRenderJob !== this.renderJobId) {
                return;
            }

            const endIndex = Math.min(startIndex + this.renderChunkSize, totalIcons);
            const html = this.filteredIcons
                .slice(startIndex, endIndex)
                .map((icon) => this.renderIconCard(icon))
                .join("");

            if (html) {
                grid.insertAdjacentHTML("beforeend", html);
            }

            if (endIndex < totalIcons) {
                requestAnimationFrame(() => appendChunk(endIndex));
            }
        };

        appendChunk(0);
    }

    renderIconCard(icon) {
        const styleMode = this.getActiveStyleMode();
        const preview = this.getCachedPreviewForMode(icon, styleMode);
        const isVisible = this.matchesStyleModeForIcon(icon, styleMode);
        const escapedName = this.escapeHtmlAttribute(icon.name);
        const hiddenStyle = isVisible ? "" : ' style="display:none;"';

        return `
            <div class="icon-card"
                data-icon-name="${escapedName}"
                data-preview-mode="${styleMode}"
                ${hiddenStyle}
                onclick="iconBrowser.openModal('${icon.name}')">
                <div class="icon-view ${preview.colorClass}">
                    ${preview.markup}
                </div>
                <div class="icon-name">${this.formatName(icon.name)}</div>
            </div>
        `;
    }

    formatName(name) {
        return name
            .split("_")
            .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
            .join(" ");
    }

    configureVariantControls(variant, variantData) {
        const controls = document.getElementById(`${variant}Controls`);
        const sizeSelect = document.getElementById(`${variant}Size`);
        const cdnLink = document.getElementById(`${variant}CdnLink`);
        const downloadOptions = document.getElementById(`${variant}DownloadOptions`);
        const currentColorToggle = document.getElementById(`${variant}CurrentColor`);

        if (!controls || !sizeSelect || !cdnLink || !downloadOptions || !currentColorToggle) {
            return;
        }

        if (this.isLegacyVariantData(variantData)) {
            controls.style.display = "none";
            downloadOptions.style.display = "none";
            sizeSelect.innerHTML = "";
            cdnLink.removeAttribute("href");
            cdnLink.classList.add("disabled");
            return;
        }

        const sizes = this.getVariantSizes(variantData);
        const defaultSize = this.getDefaultSize(variantData);
        sizeSelect.innerHTML = sizes
            .map((entrySize) => `<option value="${entrySize}">${entrySize}</option>`)
            .join("");
        if (defaultSize) {
            sizeSelect.value = String(defaultSize);
        }

        controls.style.display = sizes.length > 0 ? "flex" : "none";
        downloadOptions.style.display = "block";

        if (variant === "color") {
            currentColorToggle.checked = false;
            currentColorToggle.disabled = true;
        } else {
            currentColorToggle.disabled = false;
        }
    }

    shouldUseCurrentColorOnDownload(variant) {
        if (variant === "color") {
            return false;
        }

        const toggle = document.getElementById(`${variant}CurrentColor`);
        return Boolean(toggle?.checked);
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
        const cdnLink = document.getElementById(`${variant}CdnLink`);
        const sizeSelect = document.getElementById(`${variant}Size`);
        const colorClass = variant === "color" ? "has-color-variant" : "";

        iconDiv.className = `icon-view ${colorClass} icon-large`;

        const selectedSize = sizeSelect?.value ? Number(sizeSelect.value) : null;
        const asset = this.resolveVariantAsset(variantData, selectedSize);

        if (!asset) {
            iconDiv.innerHTML = '<div style="color: #ccc;">No preview</div>';
            cdnLink.removeAttribute("href");
            cdnLink.classList.add("disabled");
            return;
        }

        if (asset.svg) {
            iconDiv.innerHTML = asset.svg;
        } else if (asset.url) {
            const label = `${this.formatName(this.currentIcon.name)} ${variant}`;
            const escapedLabel = this.escapeHtmlAttribute(label);
            iconDiv.innerHTML = `<img src="${asset.url}" alt="${escapedLabel}" decoding="async">`;
        } else {
            iconDiv.innerHTML = '<div style="color: #ccc;">No preview</div>';
        }

        const linkTarget = asset.sourceUrl || asset.url;
        if (linkTarget) {
            cdnLink.href = linkTarget;
            cdnLink.classList.remove("disabled");
        } else {
            cdnLink.removeAttribute("href");
            cdnLink.classList.add("disabled");
        }
    }

    openModal(iconName) {
        const icon = this.icons.find((entry) => entry.name === iconName);
        if (!icon) {
            return;
        }

        this.currentIcon = icon;
        document.getElementById("modalTitle").textContent =
            icon.displayName || this.formatName(icon.name);
        document.getElementById("modalDescription").textContent =
            icon.description || "No description available";

        ["regular", "filled", "color"].forEach((variant) => {
            const variantDiv = document.getElementById(`${variant}Variant`);
            const variantData = this.getVariantData(icon, variant);

            if (variantData) {
                variantDiv.style.display = "block";
                this.configureVariantControls(variant, variantData);
                this.updateModalVariantPreview(variant);
            } else {
                variantDiv.style.display = "none";
            }
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
            metaphorsList.innerHTML = '<p style="color: #605e5c;">No metaphors available</p>';
        }

        document.getElementById("iconModal").style.display = "flex";
    }

    getVariantSelection(variant) {
        if (!this.currentIcon) {
            return null;
        }

        const variantData = this.getVariantData(this.currentIcon, variant);
        if (!variantData) {
            return null;
        }

        const sizeSelect = document.getElementById(`${variant}Size`);
        const selectedSize = sizeSelect?.value ? Number(sizeSelect.value) : null;
        const asset = this.resolveVariantAsset(variantData, selectedSize);
        if (!asset) {
            return null;
        }

        return {
            svgText: asset.svg,
            sourceUrl: asset.url,
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
    }

    showError(message) {
        const grid = document.getElementById("iconGrid");
        grid.innerHTML = `<div class="no-results">${message}</div>`;
    }
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

    const originalText = button.textContent;
    button.textContent = success ? "Done" : "Error";
    button.style.background = success ? "#107c10" : "#a4262c";

    setTimeout(() => {
        button.textContent = originalText;
        button.style.background = "#0078d4";
    }, 1500);
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

async function copyToClipboard(clickEvent, variant) {
    const selection = iconBrowser.getVariantSelection(variant);
    if (!selection) {
        return;
    }

    const button = clickEvent?.currentTarget || clickEvent?.target;

    try {
        const svgText = selection.svgText || (await fetchSvgText(selection.sourceUrl));
        await navigator.clipboard.writeText(svgText);
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
        const originalSvg = selection.svgText || (await fetchSvgText(selection.sourceUrl));
        const applyCurrentColor = iconBrowser.shouldUseCurrentColorOnDownload(variant);
        const finalSvg = applyCurrentColor ? toCurrentColorSvg(originalSvg) : originalSvg;

        const blob = new Blob([finalSvg], { type: "image/svg+xml" });
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        const sizePart = selection.size ? `_${selection.size}` : "";
        const suffix = applyCurrentColor ? "_currentcolor" : "";

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
document.addEventListener("DOMContentLoaded", () => {
    iconBrowser = new IconBrowser();
});
