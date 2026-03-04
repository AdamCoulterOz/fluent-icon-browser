class IconBrowser {
    constructor() {
        this.icons = [];
        this.filteredIcons = [];
        this.currentIcon = null;
        this.init();
    }

    getActiveFilters() {
        return {
            regular: document.getElementById("filterRegular").checked,
            filled: document.getElementById("filterFilled").checked,
            color: document.getElementById("filterColor").checked,
        };
    }

    async init() {
        await this.loadIcons();
        this.setupEventListeners();
        this.renderIcons();
        this.updateStats();
    }

    async loadIcons() {
        try {
            const response = await fetch("./icon-data.json");
            if (!response.ok) {
                throw new Error(`Failed to fetch icon data: ${response.status}`);
            }

            const payload = await response.json();
            this.icons = Array.isArray(payload) ? payload : payload.icons || [];
            this.filteredIcons = [...this.icons];
        } catch (error) {
            console.error("Error loading icons:", error);
            this.showError("Failed to load icons. Please make sure icon-data.json exists.");
        }
    }

    setupEventListeners() {
        const searchInput = document.getElementById("searchInput");
        const filterRegular = document.getElementById("filterRegular");
        const filterFilled = document.getElementById("filterFilled");
        const filterColor = document.getElementById("filterColor");
        const modal = document.getElementById("iconModal");
        const closeBtn = document.querySelector(".close");

        searchInput.addEventListener("input", (event) => {
            this.filterIcons(event.target.value);
        });

        [filterRegular, filterFilled, filterColor].forEach((filter) => {
            filter.addEventListener("change", () => {
                this.filterIcons(searchInput.value);
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

    getVariantData(icon, variant) {
        return icon?.variants?.[variant] || null;
    }

    hasVariant(icon, variant) {
        return Boolean(this.getVariantData(icon, variant));
    }

    isLegacyVariantData(variantData) {
        return typeof variantData === "string";
    }

    getVariantSizes(variantData) {
        if (!variantData || this.isLegacyVariantData(variantData)) {
            return [];
        }

        return Object.keys(variantData.sizes || {})
            .map((value) => Number(value))
            .filter((value) => Number.isFinite(value))
            .sort((a, b) => a - b);
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

    resolveVariantUrl(variantData, size) {
        if (!variantData || this.isLegacyVariantData(variantData)) {
            return null;
        }

        if (size && variantData.sizes?.[String(size)]) {
            return variantData.sizes[String(size)];
        }

        const defaultSize = this.getDefaultSize(variantData);
        if (defaultSize && variantData.sizes?.[String(defaultSize)]) {
            return variantData.sizes[String(defaultSize)];
        }

        if (typeof variantData.previewUrl === "string" && variantData.previewUrl) {
            return variantData.previewUrl;
        }

        const firstSize = Object.keys(variantData.sizes || {})[0];
        return firstSize ? variantData.sizes[firstSize] : null;
    }

    renderPreviewMarkup(icon, variant, variantData) {
        if (this.isLegacyVariantData(variantData)) {
            return variantData;
        }

        const url = this.resolveVariantUrl(variantData, variantData.defaultSize);
        if (!url) {
            return '<div style="color: #ccc;">No preview</div>';
        }

        const label = `${this.formatName(icon.name)} ${variant}`;
        return `<img src="${url}" alt="${label}" loading="lazy" decoding="async">`;
    }

    filterIcons(searchTerm) {
        const { regular: regularFilter, filled: filledFilter, color: colorFilter } = this.getActiveFilters();

        this.filteredIcons = this.icons.filter((icon) => {
            const searchMatch =
                searchTerm === "" ||
                icon.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                (icon.description &&
                    icon.description.toLowerCase().includes(searchTerm.toLowerCase())) ||
                (icon.metaphors &&
                    icon.metaphors.some((metaphor) =>
                        String(metaphor).toLowerCase().includes(searchTerm.toLowerCase())
                    ));

            const anyFilterSelected = Object.values(this.getActiveFilters()).some(Boolean);
            const styleMatch =
                !anyFilterSelected ||
                (regularFilter && this.hasVariant(icon, "regular")) ||
                (filledFilter && this.hasVariant(icon, "filled")) ||
                (colorFilter && this.hasVariant(icon, "color"));

            return searchMatch && styleMatch;
        });

        this.renderIcons();
        this.updateStats();
    }

    renderIcons() {
        const grid = document.getElementById("iconGrid");

        if (this.filteredIcons.length === 0) {
            grid.innerHTML = '<div class="no-results">No icons found matching your criteria.</div>';
            return;
        }

        grid.innerHTML = this.filteredIcons.map((icon) => this.renderIconCard(icon)).join("");
    }

    renderIconCard(icon) {
        const filters = this.getActiveFilters();
        const enabledVariants = Object.keys(filters).filter((variant) => filters[variant]);

        let previewVariant = null;
        for (const variant of ["regular", "filled", "color"]) {
            if (enabledVariants.includes(variant) && this.hasVariant(icon, variant)) {
                previewVariant = variant;
                break;
            }
        }

        if (!previewVariant) {
            previewVariant = ["regular", "filled", "color"].find((variant) =>
                this.hasVariant(icon, variant)
            );
        }

        const variantData = previewVariant ? this.getVariantData(icon, previewVariant) : null;
        const previewMarkup = variantData
            ? this.renderPreviewMarkup(icon, previewVariant, variantData)
            : '<div style="color: #ccc;">No preview</div>';
        const colorClass = previewVariant === "color" ? "has-color-variant" : "";

        return `
            <div class="icon-card" onclick="iconBrowser.openModal('${icon.name}')">
                <div class="icon-view ${colorClass}">
                    ${previewMarkup}
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
            .map((size) => `<option value="${size}">${size}</option>`)
            .join("");
        if (defaultSize) {
            sizeSelect.value = String(defaultSize);
        }

        controls.style.display = "flex";
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

        if (this.isLegacyVariantData(variantData)) {
            iconDiv.innerHTML = variantData;
            cdnLink.removeAttribute("href");
            cdnLink.classList.add("disabled");
            return;
        }

        const selectedSize = sizeSelect?.value ? Number(sizeSelect.value) : null;
        const previewUrl = this.resolveVariantUrl(variantData, selectedSize);

        if (previewUrl) {
            const label = `${this.formatName(this.currentIcon.name)} ${variant}`;
            iconDiv.innerHTML = `<img src="${previewUrl}" alt="${label}" decoding="async">`;
            cdnLink.href = previewUrl;
            cdnLink.classList.remove("disabled");
        } else {
            iconDiv.innerHTML = '<div style="color: #ccc;">No preview</div>';
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
        document.getElementById("modalTitle").textContent = this.formatName(icon.name);
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

        if (this.isLegacyVariantData(variantData)) {
            return {
                svgText: variantData,
                sourceUrl: null,
                size: null,
            };
        }

        const sizeSelect = document.getElementById(`${variant}Size`);
        const selectedSize = sizeSelect?.value ? Number(sizeSelect.value) : null;
        const resolvedUrl = this.resolveVariantUrl(variantData, selectedSize);
        const defaultSize = this.getDefaultSize(variantData);

        return {
            svgText: null,
            sourceUrl: resolvedUrl,
            size: selectedSize || defaultSize,
        };
    }

    updateStats() {
        const count = this.filteredIcons.length;
        const total = this.icons.length;
        document.getElementById("iconCount").textContent = `Showing ${count} of ${total} icons`;
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
        throw new Error(`Failed to fetch SVG from CDN (${response.status})`);
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
