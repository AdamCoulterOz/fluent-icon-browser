class IconBrowser {
    constructor() {
        this.icons = [];
        this.filteredIcons = [];
        this.currentIcon = null;
        this.init();
    }

    /**
     * Returns the current state of the three style‑filter checkboxes.
     */
    getActiveFilters() {
        return {
            regular: document.getElementById('filterRegular').checked,
            filled:  document.getElementById('filterFilled').checked,
            color:   document.getElementById('filterColor').checked
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
            // Load icons from the icon-data.json file
            const response = await fetch('./icon-data.json');
            if (!response.ok) {
                throw new Error(`Failed to fetch icon data: ${response.status}`);
            }
            this.icons = await response.json();
            this.filteredIcons = [...this.icons];
        } catch (error) {
            console.error('Error loading icons:', error);
            this.showError('Failed to load icons. Please make sure icon-data.json exists.');
        }
    }

    async generateIconData() {
        // This will be called by a separate script to generate the icon data
        console.log('Icon data needs to be generated. Please run the generate script first.');
    }

    setupEventListeners() {
        const searchInput = document.getElementById('searchInput');
        const filterRegular = document.getElementById('filterRegular');
        const filterFilled = document.getElementById('filterFilled');
        const filterColor = document.getElementById('filterColor');
        const modal = document.getElementById('iconModal');
        const closeBtn = document.querySelector('.close');

        searchInput.addEventListener('input', (e) => {
            this.filterIcons(e.target.value);
        });

        [filterRegular, filterFilled, filterColor].forEach(filter => {
            filter.addEventListener('change', () => {
                this.filterIcons(searchInput.value);
            });
        });

        closeBtn.addEventListener('click', () => {
            modal.style.display = 'none';
        });

        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.style.display = 'none';
            }
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                modal.style.display = 'none';
            }
        });
    }

    filterIcons(searchTerm) {
        const { regular: regularFilter, filled: filledFilter, color: colorFilter } = this.getActiveFilters();

        this.filteredIcons = this.icons.filter(icon => {
            // Search filter
            const searchMatch = searchTerm === '' ||
                icon.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                (icon.description && icon.description.toLowerCase().includes(searchTerm.toLowerCase())) ||
                (icon.metaphors && icon.metaphors.some(metaphor =>
                    metaphor.toLowerCase().includes(searchTerm.toLowerCase())
                ));

            // Style filter - if no filters are selected, show all
            const anyFilterSelected = Object.values(this.getActiveFilters()).some(Boolean);
            const styleMatch = !anyFilterSelected ||
                (regularFilter && icon.variants.regular) ||
                (filledFilter && icon.variants.filled) ||
                (colorFilter && icon.variants.color);

            return searchMatch && styleMatch;
        });

        this.renderIcons();
        this.updateStats();
    }

    renderIcons() {
        const grid = document.getElementById('iconGrid');

        if (this.filteredIcons.length === 0) {
            grid.innerHTML = '<div class="no-results">No icons found matching your criteria.</div>';
            return;
        }

        grid.innerHTML = this.filteredIcons.map(icon => this.renderIconCard(icon)).join('');
    }

    renderIconCard(icon) {
        const variantBadges = Object.keys(icon.variants)
            .filter(variant => icon.variants[variant])
            .map(variant => `<span class="variant-badge ${variant}">${variant}</span>`)
            .join('');

        // Determine which variant to show in the grid preview
        const filters = this.getActiveFilters();

        let previewVariant = null;
        let previewVariantType = null;

        // Only consider variants that are both present and not filtered out
        const enabledVariants = Object.keys(filters).filter(v => filters[v]);

        for (const variant of ['regular', 'filled', 'color']) {
            if (enabledVariants.includes(variant) && icon.variants[variant]) {
                previewVariant = icon.variants[variant];
                previewVariantType = variant;
                break;
            }
        }

        // Fallback: first available in order
        if (!previewVariant) {
            previewVariant = icon.variants.regular || icon.variants.filled || icon.variants.color;
        }

        // Determine if this is a color icon for proper dark mode handling
        const isColor = previewVariantType === 'color';
        const colorClass = isColor ? 'has-color-variant' : '';

        return `
            <div class="icon-card" onclick="iconBrowser.openModal('${icon.name}')">
                <div class="icon-view ${colorClass}">
                    ${previewVariant ? previewVariant : '<div style="color: #ccc;">No preview</div>'}
                </div>
                <div class="icon-name">${this.formatName(icon.name)}</div>
            </div>
        `;

                //         <div class="icon-variants">
                //     ${variantBadges}
                // </div>
    }

    formatName(name) {
        return name.split('_').map(word =>
            word.charAt(0).toUpperCase() + word.slice(1)
        ).join(' ');
    }

    openModal(iconName) {
        const icon = this.icons.find(i => i.name === iconName);
        if (!icon) return;

        this.currentIcon = icon;

        document.getElementById('modalTitle').textContent = this.formatName(icon.name);
        document.getElementById('modalDescription').textContent = icon.description || 'No description available';

        // Show/hide variants
        ['regular', 'filled', 'color'].forEach(variant => {
            const variantDiv = document.getElementById(`${variant}Variant`);
            const iconDiv = document.getElementById(`${variant}Icon`);
            if (icon.variants[variant]) {
                variantDiv.style.display = 'block';
                // Determine if this is a color icon for proper dark mode handling
                const isColor = variant === 'color';
                const svgContent = icon.variants[variant];
                const colorClass = isColor ? 'has-color-variant' : '';
                iconDiv.className = `icon-view ${colorClass} icon-large`;
                iconDiv.innerHTML = svgContent;

                // Replace the icon-actions div content with the new compact icon-button markup
                const iconActionsDiv = variantDiv.querySelector('.icon-actions');
                if (iconActionsDiv) {
                    iconActionsDiv.innerHTML = `
                        <button class="icon-btn icon-clipboard"
                                onclick="copyToClipboard(event, '${variant}')"
                                title="Copy SVG"></button>

                        <button class="icon-btn icon-download"
                                onclick="downloadIcon('${variant}')"
                                title="Download SVG"></button>
                    `;
                }
            } else {
                variantDiv.style.display = 'none';
            }
        });

        // Show metaphors
        const metaphorsList = document.getElementById('metaphorsList');
        if (icon.metaphors && icon.metaphors.length > 0) {
            metaphorsList.innerHTML = `
                <div class="metaphors-list">
                    ${icon.metaphors.map(metaphor =>
                `<span class="metaphor-tag">${metaphor}</span>`
            ).join('')}
                </div>
            `;
        } else {
            metaphorsList.innerHTML = '<p style="color: #605e5c;">No metaphors available</p>';
        }

        document.getElementById('iconModal').style.display = 'flex';
    }

    updateStats() {
        const count = this.filteredIcons.length;
        const total = this.icons.length;
        document.getElementById('iconCount').textContent =
            `Showing ${count} of ${total} icons`;
    }

    showError(message) {
        const grid = document.getElementById('iconGrid');
        grid.innerHTML = `<div class="no-results">${message}</div>`;
    }
}

// Global functions for modal actions
function copyToClipboard(clickEvent, variant) {
    if (!iconBrowser.currentIcon) return;

    const svgContent = iconBrowser.currentIcon.variants[variant];
    if (!svgContent) return;

    navigator.clipboard.writeText(svgContent).then(() => {
        // Visual feedback
        const button = clickEvent?.currentTarget || clickEvent?.target;
        if (!button) return;

        const originalText = button.textContent;
        button.textContent = 'Copied!';
        button.style.background = '#107c10';

        setTimeout(() => {
            button.textContent = originalText;
            button.style.background = '#0078d4';
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy SVG:', err);
    });
}

function downloadIcon(variant) {
    if (!iconBrowser.currentIcon) return;

    const svgContent = iconBrowser.currentIcon.variants[variant];
    if (!svgContent) return;

    const blob = new Blob([svgContent], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${iconBrowser.currentIcon.name}_${variant}.svg`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// Initialize the app
let iconBrowser;
document.addEventListener('DOMContentLoaded', () => {
    iconBrowser = new IconBrowser();
});
