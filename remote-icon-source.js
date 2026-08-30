(function (global) {
    "use strict";

    const ACTIVE_OR_EXTERNAL_ELEMENTS = new Set([
        "a",
        "animate",
        "animatemotion",
        "animatetransform",
        "audio",
        "base",
        "canvas",
        "embed",
        "foreignobject",
        "iframe",
        "image",
        "link",
        "meta",
        "mpath",
        "object",
        "script",
        "set",
        "style",
        "use",
        "video",
    ]);
    const SAFE_STYLE_PRESENTATION_PROPERTIES = new Set([
        "color",
        "display",
        "fill",
        "fill-opacity",
        "fill-rule",
        "flood-color",
        "flood-opacity",
        "lighting-color",
        "opacity",
        "stop-color",
        "stop-opacity",
        "stroke",
        "stroke-dasharray",
        "stroke-dashoffset",
        "stroke-linecap",
        "stroke-linejoin",
        "stroke-miterlimit",
        "stroke-opacity",
        "stroke-width",
        "visibility",
    ]);
    const LOCAL_FRAGMENT_URL = /^url\s*\(\s*#[-\w:.]+\s*\)$/i;

    function splitStyleDeclarations(styleText) {
        const declarations = [];
        let declarationStart = 0;
        let parenthesisDepth = 0;
        let quote = null;

        for (let index = 0; index < styleText.length; index += 1) {
            const character = styleText[index];
            if (quote) {
                if (character === quote) {
                    quote = null;
                }
                continue;
            }
            if (character === "\"" || character === "'") {
                quote = character;
                continue;
            }
            if (character === "(") {
                parenthesisDepth += 1;
                continue;
            }
            if (character === ")") {
                parenthesisDepth -= 1;
                if (parenthesisDepth < 0) {
                    return [];
                }
                continue;
            }
            if (character === ";" && parenthesisDepth === 0) {
                declarations.push(styleText.slice(declarationStart, index));
                declarationStart = index + 1;
            }
        }

        if (quote || parenthesisDepth !== 0) {
            return [];
        }
        declarations.push(styleText.slice(declarationStart));
        return declarations;
    }

    function findStyleDeclarationSeparator(declaration) {
        let parenthesisDepth = 0;
        let quote = null;
        for (let index = 0; index < declaration.length; index += 1) {
            const character = declaration[index];
            if (quote) {
                if (character === quote) {
                    quote = null;
                }
                continue;
            }
            if (character === "\"" || character === "'") {
                quote = character;
                continue;
            }
            if (character === "(") {
                parenthesisDepth += 1;
                continue;
            }
            if (character === ")") {
                parenthesisDepth -= 1;
                continue;
            }
            if (character === ":" && parenthesisDepth === 0) {
                return index;
            }
        }
        return -1;
    }

    function isSafeStylePresentationValue(value) {
        const compactValue = value.toLowerCase().replace(/\s+/g, "");
        return Boolean(
            value &&
                !/[\u0000-\u001f\u007f<>"'\\{}]/.test(value) &&
                !/(?:javascript|vbscript|data):/i.test(compactValue) &&
                !/\b(?:expression|@import|-moz-binding)\s*\(/i.test(value) &&
                (!/url\s*\(/i.test(value) || LOCAL_FRAGMENT_URL.test(value))
        );
    }

    // This deliberately accepts only presentation properties that can preserve SVG paint and visibility.
    function normalizeSafeStyleDeclarations(styleText) {
        if (typeof styleText !== "string") {
            return [];
        }

        const normalizedDeclarations = new Map();
        for (const declaration of splitStyleDeclarations(styleText)) {
            const separator = findStyleDeclarationSeparator(declaration);
            if (separator === -1) {
                continue;
            }
            const property = declaration.slice(0, separator).trim().toLowerCase();
            let value = declaration.slice(separator + 1).trim();
            if (!SAFE_STYLE_PRESENTATION_PROPERTIES.has(property)) {
                continue;
            }

            const importantMatch = /\s*!important\s*$/i.exec(value);
            const important = Boolean(importantMatch);
            if (important) {
                value = value.slice(0, importantMatch.index).trim();
            }
            if (value.includes("!") || !isSafeStylePresentationValue(value)) {
                continue;
            }

            const previous = normalizedDeclarations.get(property);
            if (!previous || important || !previous.important) {
                normalizedDeclarations.set(property, { value, important });
            }
        }

        return [...normalizedDeclarations].map(([property, declaration]) => [property, declaration.value]);
    }

    function isWhitespace(character) {
        return /\s/.test(character);
    }

    function skipWhitespaceAndComments(source, index) {
        let position = index;
        while (position < source.length) {
            if (isWhitespace(source[position])) {
                position += 1;
                continue;
            }
            if (source.startsWith("//", position)) {
                const newline = source.indexOf("\n", position + 2);
                position = newline === -1 ? source.length : newline + 1;
                continue;
            }
            if (source.startsWith("/*", position)) {
                const end = source.indexOf("*/", position + 2);
                if (end === -1) {
                    throw new Error("Unterminated comment in AMD source");
                }
                position = end + 2;
                continue;
            }
            break;
        }
        return position;
    }

    function readJavaScriptString(source, index) {
        const quote = source[index];
        if (quote !== "\"" && quote !== "'") {
            return null;
        }

        let value = "";
        let position = index + 1;
        while (position < source.length) {
            const character = source[position];
            if (character === quote) {
                return { value, end: position + 1 };
            }
            if (character !== "\\") {
                value += character;
                position += 1;
                continue;
            }

            position += 1;
            if (position >= source.length) {
                throw new Error("Unterminated escape sequence in AMD source");
            }
            const escape = source[position];
            const escapedCharacters = {
                "\"": "\"",
                "'": "'",
                "\\": "\\",
                b: "\b",
                f: "\f",
                n: "\n",
                r: "\r",
                t: "\t",
                v: "\v",
                0: "\0",
            };
            if (Object.prototype.hasOwnProperty.call(escapedCharacters, escape)) {
                value += escapedCharacters[escape];
                position += 1;
                continue;
            }
            if (escape === "x") {
                const hex = source.slice(position + 1, position + 3);
                if (!/^[0-9a-f]{2}$/i.test(hex)) {
                    throw new Error("Invalid hexadecimal escape in AMD source");
                }
                value += String.fromCharCode(Number.parseInt(hex, 16));
                position += 3;
                continue;
            }
            if (escape === "u") {
                if (source[position + 1] === "{") {
                    const close = source.indexOf("}", position + 2);
                    const codePoint = source.slice(position + 2, close);
                    if (close === -1 || !/^[0-9a-f]{1,6}$/i.test(codePoint)) {
                        throw new Error("Invalid Unicode escape in AMD source");
                    }
                    value += String.fromCodePoint(Number.parseInt(codePoint, 16));
                    position = close + 1;
                    continue;
                }
                const hex = source.slice(position + 1, position + 5);
                if (!/^[0-9a-f]{4}$/i.test(hex)) {
                    throw new Error("Invalid Unicode escape in AMD source");
                }
                value += String.fromCharCode(Number.parseInt(hex, 16));
                position += 5;
                continue;
            }
            if (escape === "\n") {
                position += 1;
                continue;
            }
            if (escape === "\r") {
                position += source[position + 1] === "\n" ? 2 : 1;
                continue;
            }

            value += escape;
            position += 1;
        }
        throw new Error("Unterminated string in AMD source");
    }

    function findClosingParenthesis(source, openIndex) {
        let depth = 0;
        let position = openIndex;
        while (position < source.length) {
            const character = source[position];
            if (character === "\"" || character === "'") {
                const string = readJavaScriptString(source, position);
                position = string.end;
                continue;
            }
            if (source.startsWith("//", position)) {
                const newline = source.indexOf("\n", position + 2);
                position = newline === -1 ? source.length : newline + 1;
                continue;
            }
            if (source.startsWith("/*", position)) {
                const end = source.indexOf("*/", position + 2);
                if (end === -1) {
                    throw new Error("Unterminated comment in AMD source");
                }
                position = end + 2;
                continue;
            }
            if (character === "(") {
                depth += 1;
            } else if (character === ")") {
                depth -= 1;
                if (depth === 0) {
                    return position;
                }
            }
            position += 1;
        }
        throw new Error("Unterminated AMD define call");
    }

    function readStaticAmdSvgString(source) {
        const staticValues = [];
        let position = 0;
        while (position < source.length) {
            const character = source[position];
            if (character === "\"" || character === "'") {
                position = readJavaScriptString(source, position).end;
                continue;
            }
            if (source.startsWith("//", position) || source.startsWith("/*", position)) {
                position = skipWhitespaceAndComments(source, position);
                continue;
            }
            if (
                source.startsWith("return", position) &&
                !/[A-Za-z0-9_$]/.test(source[position - 1] || "") &&
                !/[A-Za-z0-9_$]/.test(source[position + 6] || "")
            ) {
                const valueStart = skipWhitespaceAndComments(source, position + 6);
                const string = readJavaScriptString(source, valueStart);
                if (!string) {
                    position += 6;
                    continue;
                }
                const afterValue = skipWhitespaceAndComments(source, string.end);
                if (source[afterValue] === ";" || source[afterValue] === "}") {
                    staticValues.push(string.value);
                }
                position = string.end;
                continue;
            }
            if (
                source.startsWith("data", position) &&
                !/[A-Za-z0-9_$]/.test(source[position - 1] || "") &&
                !/[A-Za-z0-9_$]/.test(source[position + 4] || "")
            ) {
                const assignmentStart = skipWhitespaceAndComments(source, position + 4);
                if (source[assignmentStart] !== "=" || source[assignmentStart + 1] === "=") {
                    position += 4;
                    continue;
                }
                const valueStart = skipWhitespaceAndComments(source, assignmentStart + 1);
                const string = readJavaScriptString(source, valueStart);
                if (!string) {
                    position += 4;
                    continue;
                }
                const afterValue = skipWhitespaceAndComments(source, string.end);
                if (source[afterValue] === ";" || source[afterValue] === "}") {
                    staticValues.push(string.value);
                }
                position = string.end;
                continue;
            }
            position += 1;
        }

        if (staticValues.length !== 1) {
            throw new Error("AMD module must contain exactly one static SVG string value");
        }
        return staticValues[0];
    }

    function isAmdDefineBoundary(source, index) {
        if (index === 0) {
            return true;
        }
        const previous = source[index - 1];
        return previous === "\n" || previous === "\r" || /[;,)\]}]/.test(previous);
    }

    function findNamedAmdDefine(source, selector) {
        let position = 0;
        while (position < source.length) {
            const candidate = source.indexOf("define", position);
            if (candidate === -1) {
                return null;
            }
            position = candidate + 6;
            if (!isAmdDefineBoundary(source, candidate)) {
                continue;
            }

            const openIndex = skipWhitespaceAndComments(source, position);
            if (source[openIndex] !== "(") {
                continue;
            }
            const moduleStart = skipWhitespaceAndComments(source, openIndex + 1);
            const moduleName = readJavaScriptString(source, moduleStart);
            if (!moduleName || moduleName.value !== selector) {
                continue;
            }
            const commaIndex = skipWhitespaceAndComments(source, moduleName.end);
            if (source[commaIndex] !== ",") {
                continue;
            }
            return { openIndex, moduleEnd: moduleName.end };
        }
        return null;
    }

    function extractAmdSvgModule(source, selector) {
        if (typeof selector !== "string" || selector.length === 0) {
            throw new Error("AMD SVG source requires an exact named module selector");
        }

        const target = findNamedAmdDefine(source, selector);
        if (!target) {
            throw new Error(`AMD module '${selector}' was not found in remote source`);
        }
        const closeIndex = findClosingParenthesis(source, target.openIndex);
        return readStaticAmdSvgString(source.slice(target.moduleEnd, closeIndex));
    }

    function decodeJsonPointer(pointer) {
        if (pointer === "") {
            return [];
        }
        if (typeof pointer !== "string" || !pointer.startsWith("/")) {
            throw new Error("JSON SVG source requires an RFC 6901 pointer selector");
        }
        return pointer.slice(1).split("/").map((segment) => {
            if (/~(?:[^01]|$)/.test(segment)) {
                throw new Error("JSON pointer contains an invalid escape");
            }
            return segment.replaceAll("~1", "/").replaceAll("~0", "~");
        });
    }

    function extractJsonPointerSvg(source, selector) {
        let value;
        try {
            value = JSON.parse(source);
        } catch (error) {
            throw new Error(`Remote JSON source is invalid: ${error.message}`);
        }
        for (const segment of decodeJsonPointer(selector)) {
            if (!value || typeof value !== "object" || !Object.hasOwn(value, segment)) {
                throw new Error(`JSON pointer '${selector}' does not resolve to a value`);
            }
            value = value[segment];
        }
        if (typeof value !== "string") {
            throw new Error(`JSON pointer '${selector}' must resolve to an SVG string`);
        }
        return value;
    }

    function isRemoteSourceDescriptor(value) {
        return Boolean(
            value &&
                typeof value === "object" &&
                typeof value.url === "string" &&
                typeof value.format === "string" &&
                typeof value.selector === "string"
        );
    }

    function sanitizeSvg(svgText, domParser = new DOMParser()) {
        const document = domParser.parseFromString(svgText, "image/svg+xml");
        const root = document.documentElement;
        if (
            document.querySelector("parsererror") ||
            !root ||
            root.localName?.toLowerCase() !== "svg"
        ) {
            throw new Error("Resolved remote payload is not valid SVG");
        }

        const sanitizeAttributes = (element) => {
            [...element.attributes].forEach((attribute) => {
                const name = attribute.name.toLowerCase();
                const value = attribute.value.trim();
                const normalizedValue = value.toLowerCase().replace(/\s+/g, "");
                const hasUnsafeUrl =
                    /^\s*(?:javascript|vbscript|data):/i.test(value) ||
                    (/url\s*\(/i.test(value) && !LOCAL_FRAGMENT_URL.test(value));
                if (name === "style") {
                    normalizeSafeStyleDeclarations(value).forEach(([property, styleValue]) => {
                        element.setAttribute(property, styleValue);
                    });
                    element.removeAttribute(attribute.name);
                    return;
                }
                if (
                    name.startsWith("on") ||
                    name === "href" ||
                    name.endsWith(":href") ||
                    normalizedValue.includes("javascript:") ||
                    hasUnsafeUrl
                ) {
                    element.removeAttribute(attribute.name);
                }
            });
        };

        sanitizeAttributes(root);
        root.querySelectorAll("*").forEach((element) => {
            if (ACTIVE_OR_EXTERNAL_ELEMENTS.has(element.localName.toLowerCase())) {
                element.remove();
                return;
            }
            sanitizeAttributes(element);
        });
        return new XMLSerializer().serializeToString(root);
    }

    function canonicalizeSvgForDigest(svgText, domParser = new DOMParser()) {
        const document = domParser.parseFromString(svgText, "image/svg+xml");
        const root = document.documentElement;
        if (document.querySelector("parsererror") || !root || root.localName?.toLowerCase() !== "svg") {
            throw new Error("Resolved remote payload is not valid SVG");
        }

        const usedNamespacePrefixes = new Set();
        [root, ...root.querySelectorAll("*")].forEach((element) => {
            if (element.prefix) {
                usedNamespacePrefixes.add(element.prefix);
            }
            [...element.attributes].forEach((attribute) => {
                if (attribute.prefix && attribute.prefix !== "xmlns") {
                    usedNamespacePrefixes.add(attribute.prefix);
                }
            });
        });
        const escapeText = (value) => value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
        const escapeAttribute = (value) => escapeText(value).replaceAll("\"", "&quot;").replaceAll("\t", "&#x9;").replaceAll("\n", "&#xA;").replaceAll("\r", "&#xD;");
        const serializeNode = (node) => {
            if (node.nodeType === Node.TEXT_NODE) {
                return escapeText(node.nodeValue.trim());
            }
            if (node.nodeType !== Node.ELEMENT_NODE) {
                return "";
            }
            const attributes = [...node.attributes].filter(
                (attribute) =>
                    !attribute.name.startsWith("xmlns:") ||
                    usedNamespacePrefixes.has(attribute.name.slice("xmlns:".length))
            ).sort((left, right) => {
                const leftNamespace = left.name === "xmlns" || left.name.startsWith("xmlns:");
                const rightNamespace = right.name === "xmlns" || right.name.startsWith("xmlns:");
                if (leftNamespace !== rightNamespace) {
                    return leftNamespace ? -1 : 1;
                }
                return left.name < right.name ? -1 : left.name > right.name ? 1 : 0;
            });
            const attributesText = attributes
                .map((attribute) => ` ${attribute.name}="${escapeAttribute(attribute.value)}"`)
                .join("");
            return `<${node.tagName}${attributesText}>${[...node.childNodes].map(serializeNode).join("")}</${node.tagName}>`;
        };
        return serializeNode(root);
    }

    async function sha256Digest(text, cryptoApi = global.crypto) {
        if (!cryptoApi?.subtle || typeof TextEncoder === "undefined") {
            throw new Error("SHA-256 verification is unavailable in this browser");
        }
        const bytes = new TextEncoder().encode(text);
        const digest = await cryptoApi.subtle.digest("SHA-256", bytes);
        return new Uint8Array(digest);
    }

    function bytesToHex(bytes) {
        return [...bytes].map((value) => value.toString(16).padStart(2, "0")).join("");
    }

    function bytesToBase64(bytes) {
        let binary = "";
        bytes.forEach((value) => {
            binary += String.fromCharCode(value);
        });
        return btoa(binary);
    }

    async function verifySha256(text, expectedHash, cryptoApi) {
        if (typeof expectedHash !== "string" || expectedHash.length === 0) {
            return;
        }
        const digest = await sha256Digest(text, cryptoApi);
        const expected = expectedHash.trim();
        const actualHashes = [
            bytesToHex(digest),
            bytesToBase64(digest),
            `sha256-${bytesToBase64(digest)}`,
        ];
        if (!actualHashes.includes(expected)) {
            throw new Error("Remote source SHA-256 does not match its descriptor");
        }
    }

    function isJavaScriptOrJsonSourceUrl(url) {
        return /\.(?:js|json)(?:[?#]|$)/i.test(url);
    }

    function isHtmlResponse(response) {
        const contentType = response?.headers?.get?.("content-type");
        return typeof contentType === "string" && /(?:^|\s|;)text\/html(?:\s|;|$)|application\/xhtml\+xml/i.test(contentType);
    }

    class RemoteIconSourceResolver {
        constructor(options = {}) {
            this.fetch = options.fetch || global.fetch?.bind(global);
            this.crypto = options.crypto || global.crypto;
            this.sanitize = options.sanitize || sanitizeSvg;
            this.canonicalize = options.canonicalize || canonicalizeSvgForDigest;
            this.sourceTextByUrl = new Map();
            this.svgByDescriptor = new Map();
        }

        descriptorKey(descriptor) {
            return [descriptor.url, descriptor.format, descriptor.selector, descriptor.sha256 || ""].join("\n");
        }

        async fetchSourceText(url) {
            if (!this.fetch) {
                throw new Error("Remote icon sources cannot be fetched in this browser");
            }
            if (!this.sourceTextByUrl.has(url)) {
                const request = Promise.resolve(this.fetch(url, { credentials: "omit" })).then(async (response) => {
                    if (!response?.ok) {
                        throw new Error(`Failed to fetch remote icon source (${response?.status || "network error"})`);
                    }
                    if (isJavaScriptOrJsonSourceUrl(url) && isHtmlResponse(response)) {
                        throw new Error("Remote icon source returned HTML instead of JavaScript or JSON");
                    }
                    return response.text();
                });
                this.sourceTextByUrl.set(url, request);
                request.catch(() => {
                    if (this.sourceTextByUrl.get(url) === request) {
                        this.sourceTextByUrl.delete(url);
                    }
                });
            }
            return this.sourceTextByUrl.get(url);
        }

        extractSvg(sourceText, descriptor) {
            if (descriptor.format === "portal-amd-svg-module") {
                return extractAmdSvgModule(sourceText, descriptor.selector);
            }
            if (descriptor.format === "portal-json-pointer-svg") {
                return extractJsonPointerSvg(sourceText, descriptor.selector);
            }
            throw new Error(`Unsupported remote SVG source format '${descriptor.format}'`);
        }

        async resolve(descriptor) {
            if (!isRemoteSourceDescriptor(descriptor)) {
                throw new Error("Invalid remote SVG source descriptor");
            }
            const key = this.descriptorKey(descriptor);
            if (!this.svgByDescriptor.has(key)) {
                const resolution = this.fetchSourceText(descriptor.url).then(async (sourceText) => {
                    const extractedSvg = this.extractSvg(sourceText, descriptor);
                    const canonicalSvg = this.canonicalize(extractedSvg);
                    await verifySha256(canonicalSvg, descriptor.sha256, this.crypto);
                    return this.sanitize(extractedSvg);
                });
                this.svgByDescriptor.set(key, resolution);
                resolution.catch(() => {
                    if (this.svgByDescriptor.get(key) === resolution) {
                        this.svgByDescriptor.delete(key);
                    }
                });
            }
            return this.svgByDescriptor.get(key);
        }
    }

    const exports = {
        RemoteIconSourceResolver,
        decodeJsonPointer,
        extractAmdSvgModule,
        extractJsonPointerSvg,
        isRemoteSourceDescriptor,
        normalizeSafeStyleDeclarations,
        sanitizeSvg,
        canonicalizeSvgForDigest,
        verifySha256,
    };
    global.RemoteIconSource = exports;
    if (typeof module !== "undefined" && module.exports) {
        module.exports = exports;
    }
})(typeof window !== "undefined" ? window : globalThis);
