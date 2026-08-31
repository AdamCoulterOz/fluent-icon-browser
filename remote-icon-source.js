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
    const PAINT_MAP_CLASS = /^msportalfx-svg-c\d{2}$/;
    const PAINT_MAP_FILL = /^#[0-9a-f]{6}$/i;
    const SHA256_HEX = /^[0-9a-f]{64}$/i;
    const MAX_ZIP_ARCHIVE_BYTES = 16 * 1024 * 1024;
    const MAX_ZIP_CENTRAL_DIRECTORY_BYTES = 4 * 1024 * 1024;
    const MAX_ZIP_ENTRIES = 10000;
    const MAX_ZIP_ENTRY_COMPRESSED_BYTES = 8 * 1024 * 1024;
    const MAX_ZIP_ENTRY_UNCOMPRESSED_BYTES = 8 * 1024 * 1024;

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
                (
                    typeof value.selector === "string" ||
                    (
                        (
                            value.format === "npm-tgz-svg-entry" ||
                            value.format === "zip-svg-entry" ||
                            value.format === "same-origin-zip-svg-entry"
                        ) &&
                        typeof value.entry === "string" &&
                        typeof value.archiveSha256 === "string" &&
                        typeof value.entrySha256 === "string"
                    )
                )
        );
    }

    function normalizePaintMap(value) {
        if (!value || typeof value !== "object" || Array.isArray(value)) {
            return [];
        }
        return Object.entries(value).filter(
            ([className, fill]) =>
                PAINT_MAP_CLASS.test(className) &&
                typeof fill === "string" &&
                PAINT_MAP_FILL.test(fill)
        );
    }

    function applyPaintMap(root, paintMap) {
        if (!paintMap.length) {
            return;
        }
        [root, ...root.querySelectorAll("*")].forEach((element) => {
            const classNames = (element.getAttribute("class") || "").split(/\s+/).filter(Boolean);
            const matchedClassNames = new Set();
            paintMap.forEach(([className, fill]) => {
                if (classNames.includes(className)) {
                    element.setAttribute("fill", fill);
                    matchedClassNames.add(className);
                }
            });
            if (matchedClassNames.size) {
                const remainingClassNames = classNames.filter(
                    (className) => !matchedClassNames.has(className)
                );
                if (remainingClassNames.length) {
                    element.setAttribute("class", remainingClassNames.join(" "));
                } else {
                    element.removeAttribute("class");
                }
            }
        });
    }

    function sanitizeSvg(svgText, domParser = new DOMParser(), paintMap = null) {
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
        applyPaintMap(root, normalizePaintMap(paintMap));
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

    async function verifySha256Bytes(bytes, expectedHash, cryptoApi) {
        if (typeof expectedHash !== "string" || expectedHash.length === 0) {
            return;
        }
        if (!cryptoApi?.subtle) {
            throw new Error("SHA-256 verification is unavailable in this browser");
        }
        const value = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
        const digest = new Uint8Array(await cryptoApi.subtle.digest("SHA-256", value));
        if (bytesToHex(digest) !== expectedHash.trim().toLowerCase()) {
            throw new Error("Remote archive SHA-256 does not match its descriptor");
        }
    }

    function decodeTarString(bytes, start, length) {
        const end = bytes.indexOf(0, start);
        const sliceEnd = end === -1 || end > start + length ? start + length : end;
        return new TextDecoder("utf-8", { fatal: true }).decode(bytes.slice(start, sliceEnd));
    }

    function isEmptyTarBlock(bytes, offset) {
        for (let index = offset; index < offset + 512; index += 1) {
            if (bytes[index] !== 0) {
                return false;
            }
        }
        return true;
    }

    function readTarOctal(bytes, start, length) {
        const value = decodeTarString(bytes, start, length).trim();
        if (!/^[0-7]*$/.test(value)) {
            throw new Error("Archive entry has an invalid size field");
        }
        return value ? Number.parseInt(value, 8) : 0;
    }

    function extractTarEntry(tarBytes, expectedEntry) {
        if (
            typeof expectedEntry !== "string" ||
            !expectedEntry ||
            expectedEntry.startsWith("/") ||
            expectedEntry.split("/").includes("..")
        ) {
            throw new Error("Archive SVG source requires a safe entry path");
        }
        for (let offset = 0; offset + 512 <= tarBytes.length;) {
            if (isEmptyTarBlock(tarBytes, offset)) {
                break;
            }
            const name = decodeTarString(tarBytes, offset, 100);
            const prefix = decodeTarString(tarBytes, offset + 345, 155);
            const entry = prefix ? `${prefix}/${name}` : name;
            const type = String.fromCharCode(tarBytes[offset + 156] || 48);
            const size = readTarOctal(tarBytes, offset + 124, 12);
            const contentStart = offset + 512;
            const contentEnd = contentStart + size;
            if (
                !entry ||
                entry.startsWith("/") ||
                entry.split("/").includes("..") ||
                contentEnd > tarBytes.length
            ) {
                throw new Error("Archive contains an unsafe or truncated entry");
            }
            if (entry === expectedEntry) {
                if (type !== "0" && type !== "\0") {
                    throw new Error("Requested archive entry is not a regular file");
                }
                return tarBytes.slice(contentStart, contentEnd);
            }
            offset = contentStart + Math.ceil(size / 512) * 512;
        }
        throw new Error(`Archive entry '${expectedEntry}' was not found`);
    }

    function isSafeArchiveEntryPath(entry) {
        const segments = typeof entry === "string" ? entry.split("/") : [];
        return Boolean(
            typeof entry === "string" &&
            entry &&
            !entry.startsWith("/") &&
            !entry.startsWith("\\") &&
            !/^[A-Za-z]:/.test(entry) &&
            !entry.includes("\\") &&
            segments.every((segment, index) =>
                (segment || index === segments.length - 1) && segment !== "." && segment !== ".."
            )
        );
    }

    function validateZipSvgEntryDescriptor(descriptor) {
        if (!isSafeArchiveEntryPath(descriptor.entry)) {
            throw new Error("ZIP SVG source requires a safe entry path");
        }
        if (!SHA256_HEX.test(descriptor.archiveSha256) || !SHA256_HEX.test(descriptor.entrySha256)) {
            throw new Error("ZIP SVG source requires hexadecimal SHA-256 archive and entry digests");
        }
        try {
            const url = new URL(descriptor.url);
            if (url.protocol !== "https:") {
                throw new Error("unsupported protocol");
            }
        } catch (_error) {
            throw new Error("ZIP SVG source requires an absolute HTTPS archive URL");
        }
    }

    function validateSameOriginZipSvgEntryDescriptor(descriptor, baseUrl) {
        if (!isSafeArchiveEntryPath(descriptor.entry)) {
            throw new Error("Same-origin ZIP SVG source requires a safe entry path");
        }
        if (!SHA256_HEX.test(descriptor.archiveSha256) || !SHA256_HEX.test(descriptor.entrySha256)) {
            throw new Error("Same-origin ZIP SVG source requires hexadecimal SHA-256 archive and entry digests");
        }
        if (!descriptor.url.trim()) {
            throw new Error("Same-origin ZIP SVG source requires a valid archive URL");
        }
        if (/^\s*\/\//.test(descriptor.url)) {
            throw new Error("Same-origin ZIP SVG source does not allow protocol-relative archive URLs");
        }
        let pageUrl;
        let archiveUrl;
        try {
            pageUrl = new URL(baseUrl);
            archiveUrl = new URL(descriptor.url, pageUrl);
        } catch (_error) {
            throw new Error("Same-origin ZIP SVG source requires a current page URL and a valid archive URL");
        }
        if (
            !/^https?:$/.test(pageUrl.protocol) ||
            !/^https?:$/.test(archiveUrl.protocol) ||
            archiveUrl.origin !== pageUrl.origin
        ) {
            throw new Error("Same-origin ZIP SVG source requires an HTTP(S) archive URL from the current page origin");
        }
        return archiveUrl.href;
    }

    function readZipUint16(bytes, offset, context) {
        if (offset < 0 || offset + 2 > bytes.length) {
            throw new Error(`Malformed ZIP archive: truncated ${context}`);
        }
        return bytes[offset] | (bytes[offset + 1] << 8);
    }

    function readZipUint32(bytes, offset, context) {
        if (offset < 0 || offset + 4 > bytes.length) {
            throw new Error(`Malformed ZIP archive: truncated ${context}`);
        }
        return (
            bytes[offset] +
            bytes[offset + 1] * 0x100 +
            bytes[offset + 2] * 0x10000 +
            bytes[offset + 3] * 0x1000000
        );
    }

    function zipBytesEqual(left, right) {
        return left.length === right.length && left.every((value, index) => value === right[index]);
    }

    function decodeZipEntryName(bytes) {
        let entry;
        try {
            entry = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
        } catch (_error) {
            throw new Error("Malformed ZIP archive: entry name is not valid UTF-8");
        }
        if (!isSafeArchiveEntryPath(entry)) {
            throw new Error("ZIP archive contains an unsafe entry path");
        }
        return entry;
    }

    function hasZip64ExtraField(extra) {
        for (let offset = 0; offset < extra.length;) {
            if (offset + 4 > extra.length) {
                throw new Error("Malformed ZIP archive: truncated extra field");
            }
            const fieldId = extra[offset] | (extra[offset + 1] << 8);
            const fieldLength = extra[offset + 2] | (extra[offset + 3] << 8);
            offset += 4;
            if (offset + fieldLength > extra.length) {
                throw new Error("Malformed ZIP archive: truncated extra field value");
            }
            if (fieldId === 0x0001) {
                return true;
            }
            offset += fieldLength;
        }
        return false;
    }

    function findZipEndOfCentralDirectory(bytes) {
        const minimumOffset = Math.max(0, bytes.length - 0xffff - 22);
        for (let offset = bytes.length - 22; offset >= minimumOffset; offset -= 1) {
            if (readZipUint32(bytes, offset, "end of central directory") !== 0x06054b50) {
                continue;
            }
            const commentLength = readZipUint16(bytes, offset + 20, "end of central directory comment length");
            if (offset + 22 + commentLength === bytes.length) {
                return offset;
            }
        }
        throw new Error("Malformed ZIP archive: end of central directory was not found");
    }

    function parseZipCentralDirectory(bytes) {
        if (bytes.length > MAX_ZIP_ARCHIVE_BYTES) {
            throw new Error("ZIP archive exceeds the supported size limit");
        }
        const eocdOffset = findZipEndOfCentralDirectory(bytes);
        const diskNumber = readZipUint16(bytes, eocdOffset + 4, "end of central directory disk number");
        const centralDirectoryDisk = readZipUint16(bytes, eocdOffset + 6, "central directory disk number");
        const entriesOnDisk = readZipUint16(bytes, eocdOffset + 8, "entry count");
        const entryCount = readZipUint16(bytes, eocdOffset + 10, "entry count");
        const centralDirectorySize = readZipUint32(bytes, eocdOffset + 12, "central directory size");
        const centralDirectoryOffset = readZipUint32(bytes, eocdOffset + 16, "central directory offset");
        if (
            diskNumber !== 0 ||
            centralDirectoryDisk !== 0 ||
            entriesOnDisk !== entryCount ||
            entryCount === 0xffff ||
            centralDirectorySize === 0xffffffff ||
            centralDirectoryOffset === 0xffffffff
        ) {
            throw new Error("ZIP archive uses unsupported multi-disk or ZIP64 metadata");
        }
        if (
            entryCount > MAX_ZIP_ENTRIES ||
            centralDirectorySize > MAX_ZIP_CENTRAL_DIRECTORY_BYTES ||
            centralDirectoryOffset + centralDirectorySize !== eocdOffset
        ) {
            throw new Error("Malformed ZIP archive: central directory dimensions are unsupported");
        }

        let offset = centralDirectoryOffset;
        const entriesByName = new Map();
        const entries = [];
        for (let index = 0; index < entryCount; index += 1) {
            if (readZipUint32(bytes, offset, "central directory header") !== 0x02014b50) {
                throw new Error("Malformed ZIP archive: invalid central directory header");
            }
            const flags = readZipUint16(bytes, offset + 8, "central directory flags");
            const compression = readZipUint16(bytes, offset + 10, "central directory compression method");
            const crc32 = readZipUint32(bytes, offset + 16, "central directory CRC-32");
            const compressedSize = readZipUint32(bytes, offset + 20, "central directory compressed size");
            const uncompressedSize = readZipUint32(bytes, offset + 24, "central directory uncompressed size");
            const nameLength = readZipUint16(bytes, offset + 28, "central directory name length");
            const extraLength = readZipUint16(bytes, offset + 30, "central directory extra length");
            const commentLength = readZipUint16(bytes, offset + 32, "central directory comment length");
            const diskStart = readZipUint16(bytes, offset + 34, "central directory disk start");
            const localHeaderOffset = readZipUint32(bytes, offset + 42, "central directory local header offset");
            const recordEnd = offset + 46 + nameLength + extraLength + commentLength;
            if (recordEnd > eocdOffset) {
                throw new Error("Malformed ZIP archive: truncated central directory entry");
            }
            const nameBytes = bytes.slice(offset + 46, offset + 46 + nameLength);
            const extra = bytes.slice(offset + 46 + nameLength, offset + 46 + nameLength + extraLength);
            const entry = decodeZipEntryName(nameBytes);
            if (
                (flags & 0x0041) !== 0 ||
                compression !== 0 && compression !== 8 ||
                diskStart !== 0 ||
                localHeaderOffset === 0xffffffff ||
                localHeaderOffset >= centralDirectoryOffset ||
                hasZip64ExtraField(extra)
            ) {
                throw new Error("ZIP archive uses encrypted, ZIP64, or unsupported compression metadata");
            }
            if (
                compressedSize > MAX_ZIP_ENTRY_COMPRESSED_BYTES ||
                uncompressedSize > MAX_ZIP_ENTRY_UNCOMPRESSED_BYTES
            ) {
                throw new Error("ZIP archive entry exceeds the supported size limit");
            }
            const metadata = {
                flags,
                usesDataDescriptor: Boolean(flags & 0x0008),
                compression,
                crc32,
                compressedSize,
                uncompressedSize,
                nameBytes,
                localHeaderOffset,
                centralDirectoryOffset,
            };
            const sameNameEntries = entriesByName.get(entry) || [];
            sameNameEntries.push(metadata);
            entriesByName.set(entry, sameNameEntries);
            entries.push(metadata);
            offset = recordEnd;
        }
        if (offset !== eocdOffset) {
            throw new Error("Malformed ZIP archive: central directory size does not match its entries");
        }
        const entriesByOffset = [...entries].sort(
            (left, right) => left.localHeaderOffset - right.localHeaderOffset
        );
        let nextLocalHeaderOffset = centralDirectoryOffset;
        for (let index = entriesByOffset.length - 1; index >= 0;) {
            const localHeaderOffset = entriesByOffset[index].localHeaderOffset;
            let groupStart = index;
            while (
                groupStart > 0 &&
                entriesByOffset[groupStart - 1].localHeaderOffset === localHeaderOffset
            ) {
                groupStart -= 1;
            }
            for (let groupedIndex = groupStart; groupedIndex <= index; groupedIndex += 1) {
                entriesByOffset[groupedIndex].nextLocalHeaderOffset = nextLocalHeaderOffset;
            }
            nextLocalHeaderOffset = localHeaderOffset;
            index = groupStart - 1;
        }
        return entriesByName;
    }

    function crc32(bytes) {
        let crc = 0xffffffff;
        for (const value of bytes) {
            crc ^= value;
            for (let bit = 0; bit < 8; bit += 1) {
                crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1));
            }
        }
        return (crc ^ 0xffffffff) >>> 0;
    }

    async function decompressZipDeflate(compressedBytes, expectedLength) {
        if (typeof DecompressionStream === "undefined") {
            throw new Error("This browser cannot decompress the required deflate ZIP entry");
        }
        let reader;
        try {
            reader = new Blob([compressedBytes]).stream()
                .pipeThrough(new DecompressionStream("deflate-raw"))
                .getReader();
        } catch (_error) {
            throw new Error("This browser cannot decompress the required deflate ZIP entry");
        }
        const chunks = [];
        let length = 0;
        try {
            for (;;) {
                const { done, value } = await reader.read();
                if (done) {
                    break;
                }
                length += value.length;
                if (length > MAX_ZIP_ENTRY_UNCOMPRESSED_BYTES || length > expectedLength) {
                    throw new Error("ZIP archive entry exceeds the supported size limit");
                }
                chunks.push(value);
            }
        } catch (error) {
            await reader.cancel(error).catch(() => {});
            throw error;
        } finally {
            reader.releaseLock();
        }
        if (length !== expectedLength) {
            throw new Error("Malformed ZIP archive: deflated entry length does not match metadata");
        }
        const result = new Uint8Array(length);
        let offset = 0;
        chunks.forEach((chunk) => {
            result.set(chunk, offset);
            offset += chunk.length;
        });
        return result;
    }

    async function extractZipEntry(zipBytes, expectedEntry, entriesByName) {
        if (!isSafeArchiveEntryPath(expectedEntry)) {
            throw new Error("ZIP SVG source requires a safe entry path");
        }
        const archiveEntriesByName = entriesByName || parseZipCentralDirectory(zipBytes);
        const entries = archiveEntriesByName.get(expectedEntry);
        if (!entries) {
            throw new Error(`ZIP archive entry '${expectedEntry}' was not found`);
        }
        if (entries.length !== 1) {
            throw new Error("ZIP archive contains duplicate requested entries");
        }
        const [entry] = entries;
        const headerOffset = entry.localHeaderOffset;
        if (readZipUint32(zipBytes, headerOffset, "local file header") !== 0x04034b50) {
            throw new Error("Malformed ZIP archive: requested entry has no local file header");
        }
        const flags = readZipUint16(zipBytes, headerOffset + 6, "local file header flags");
        const compression = readZipUint16(zipBytes, headerOffset + 8, "local file header compression method");
        const localCrc32 = readZipUint32(zipBytes, headerOffset + 14, "local file header CRC-32");
        const localCompressedSize = readZipUint32(zipBytes, headerOffset + 18, "local file header compressed size");
        const localUncompressedSize = readZipUint32(zipBytes, headerOffset + 22, "local file header uncompressed size");
        const nameLength = readZipUint16(zipBytes, headerOffset + 26, "local file header name length");
        const extraLength = readZipUint16(zipBytes, headerOffset + 28, "local file header extra length");
        const nameStart = headerOffset + 30;
        const dataStart = nameStart + nameLength + extraLength;
        const dataEnd = dataStart + entry.compressedSize;
        const localMetadataMatches = entry.usesDataDescriptor
            ? localCrc32 === 0 && localCompressedSize === 0 && localUncompressedSize === 0
            : (
                localCrc32 === entry.crc32 &&
                localCompressedSize === entry.compressedSize &&
                localUncompressedSize === entry.uncompressedSize
            );
        if (entry.usesDataDescriptor && !localMetadataMatches) {
            throw new Error("Malformed ZIP archive: data-descriptor metadata is ambiguous");
        }
        if (
            flags !== entry.flags ||
            compression !== entry.compression ||
            dataEnd > entry.centralDirectoryOffset ||
            hasZip64ExtraField(zipBytes.slice(nameStart + nameLength, dataStart)) ||
            !localMetadataMatches ||
            !zipBytesEqual(zipBytes.slice(nameStart, nameStart + nameLength), entry.nameBytes)
        ) {
            throw new Error("Malformed ZIP archive: local entry metadata does not match the central directory");
        }
        if (entry.usesDataDescriptor) {
            const descriptorEnd = dataEnd + 16;
            if (
                descriptorEnd !== entry.nextLocalHeaderOffset ||
                readZipUint32(zipBytes, dataEnd, "data descriptor") !== 0x08074b50 ||
                readZipUint32(zipBytes, dataEnd + 4, "data descriptor CRC-32") !== entry.crc32 ||
                readZipUint32(zipBytes, dataEnd + 8, "data descriptor compressed size") !== entry.compressedSize ||
                readZipUint32(zipBytes, dataEnd + 12, "data descriptor uncompressed size") !== entry.uncompressedSize
            ) {
                throw new Error("Malformed ZIP archive: data-descriptor metadata is ambiguous");
            }
        }
        const compressedBytes = zipBytes.slice(dataStart, dataEnd);
        const content = entry.compression === 0
            ? compressedBytes
            : await decompressZipDeflate(compressedBytes, entry.uncompressedSize);
        if (content.length !== entry.uncompressedSize || crc32(content) !== entry.crc32) {
            throw new Error("Malformed ZIP archive: entry CRC-32 or length does not match metadata");
        }
        return content;
    }

    function decodeZipSvgEntry(bytes) {
        try {
            return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
        } catch (_error) {
            throw new Error("ZIP archive entry is not valid UTF-8");
        }
    }

    async function decompressGzip(archiveBytes) {
        if (typeof DecompressionStream === "undefined") {
            throw new Error("This browser cannot decompress the required gzip icon archive");
        }
        const stream = new Blob([archiveBytes]).stream().pipeThrough(new DecompressionStream("gzip"));
        return new Uint8Array(await new Response(stream).arrayBuffer());
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
            this.baseUrl = options.baseUrl || global.location?.href;
            this.sourceTextByUrl = new Map();
            this.archiveBytesByUrl = new Map();
            this.verifiedZipArchivesByKey = new Map();
            this.svgByDescriptor = new Map();
        }

        descriptorKey(descriptor, resolvedArchiveUrl = descriptor.url) {
            return [
                resolvedArchiveUrl,
                descriptor.format,
                descriptor.selector,
                descriptor.entry || "",
                descriptor.archiveSha256 || "",
                descriptor.entrySha256 || "",
                descriptor.sha256 || "",
                JSON.stringify(normalizePaintMap(descriptor.paintMap)),
            ].join("\n");
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

        async fetchArchiveBytes(url) {
            if (!this.fetch) {
                throw new Error("Remote icon archives cannot be fetched in this browser");
            }
            if (!this.archiveBytesByUrl.has(url)) {
                const request = Promise.resolve(this.fetch(url, { credentials: "omit" })).then(async (response) => {
                    if (!response?.ok) {
                        throw new Error(`Failed to fetch remote icon archive (${response?.status || "network error"})`);
                    }
                    if (isHtmlResponse(response)) {
                        throw new Error("Remote icon archive returned HTML instead of an archive");
                    }
                    return new Uint8Array(await response.arrayBuffer());
                });
                this.archiveBytesByUrl.set(url, request);
                request.catch(() => {
                    if (this.archiveBytesByUrl.get(url) === request) {
                        this.archiveBytesByUrl.delete(url);
                    }
                });
            }
            return this.archiveBytesByUrl.get(url);
        }

        verifiedZipArchiveKey(url, archiveSha256) {
            return `${url}\n${archiveSha256}`;
        }

        async fetchVerifiedZipArchive(url, archiveSha256) {
            const key = this.verifiedZipArchiveKey(url, archiveSha256);
            if (!this.verifiedZipArchivesByKey.has(key)) {
                const verifiedArchive = this.fetchArchiveBytes(url).then(async (bytes) => {
                    await verifySha256Bytes(bytes, archiveSha256, this.crypto);
                    return {
                        bytes,
                        entriesByName: parseZipCentralDirectory(bytes),
                    };
                });
                this.verifiedZipArchivesByKey.set(key, verifiedArchive);
                verifiedArchive.catch(() => {
                    if (this.verifiedZipArchivesByKey.get(key) === verifiedArchive) {
                        this.verifiedZipArchivesByKey.delete(key);
                    }
                });
            }
            return this.verifiedZipArchivesByKey.get(key);
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
            let archiveUrl = descriptor.url;
            if (descriptor.format === "zip-svg-entry") {
                validateZipSvgEntryDescriptor(descriptor);
            } else if (descriptor.format === "same-origin-zip-svg-entry") {
                archiveUrl = validateSameOriginZipSvgEntryDescriptor(descriptor, this.baseUrl);
            }
            const key = this.descriptorKey(descriptor, archiveUrl);
            if (!this.svgByDescriptor.has(key)) {
                const resolution = descriptor.format === "npm-tgz-svg-entry"
                    ? this.fetchArchiveBytes(descriptor.url).then(async (archiveBytes) => {
                        await verifySha256Bytes(archiveBytes, descriptor.archiveSha256, this.crypto);
                        const entryBytes = extractTarEntry(await decompressGzip(archiveBytes), descriptor.entry);
                        await verifySha256Bytes(entryBytes, descriptor.entrySha256, this.crypto);
                        return this.sanitize(new TextDecoder("utf-8", { fatal: true }).decode(entryBytes));
                    })
                    : descriptor.format === "zip-svg-entry" || descriptor.format === "same-origin-zip-svg-entry"
                        ? this.fetchVerifiedZipArchive(archiveUrl, descriptor.archiveSha256).then(async (archive) => {
                            const entryBytes = await extractZipEntry(
                                archive.bytes,
                                descriptor.entry,
                                archive.entriesByName
                            );
                            await verifySha256Bytes(entryBytes, descriptor.entrySha256, this.crypto);
                            return this.sanitize(decodeZipSvgEntry(entryBytes));
                        })
                    : this.fetchSourceText(descriptor.url).then(async (sourceText) => {
                        const extractedSvg = this.extractSvg(sourceText, descriptor);
                        const canonicalSvg = this.canonicalize(extractedSvg);
                        await verifySha256(canonicalSvg, descriptor.sha256, this.crypto);
                        return this.sanitize(extractedSvg, undefined, descriptor.paintMap);
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
        normalizePaintMap,
        sanitizeSvg,
        canonicalizeSvgForDigest,
        verifySha256,
        verifySha256Bytes,
        extractTarEntry,
        extractZipEntry,
    };
    global.RemoteIconSource = exports;
    if (typeof module !== "undefined" && module.exports) {
        module.exports = exports;
    }
})(typeof window !== "undefined" ? window : globalThis);
