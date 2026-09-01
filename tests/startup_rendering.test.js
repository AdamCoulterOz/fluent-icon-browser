const assert = require("node:assert/strict");

const {
    ICON_RENDER_FIRST_BATCH_SIZE,
    ICON_RENDER_FOLLOW_UP_BATCH_SIZE,
    getProgressiveRenderBatch,
    isActiveRenderGeneration,
    isWithinRenderContinuationThreshold,
    scheduleDeferredIconCacheWarming,
} = require("../script.js");

const icons = Array.from({ length: 250 }, (_, index) => ({ name: `icon-${index}` }));
const firstBatch = getProgressiveRenderBatch(icons, 0, ICON_RENDER_FIRST_BATCH_SIZE);

assert.equal(firstBatch.length, ICON_RENDER_FIRST_BATCH_SIZE, "the first render batch must remain bounded");
assert.deepEqual(
    firstBatch,
    icons.slice(0, ICON_RENDER_FIRST_BATCH_SIZE),
    "the first batch preserves source order"
);

const rendered = [...firstBatch];
let offset = firstBatch.length;
while (offset < icons.length) {
    const batch = getProgressiveRenderBatch(icons, offset, ICON_RENDER_FOLLOW_UP_BATCH_SIZE);
    assert.ok(
        batch.length > 0 && batch.length <= ICON_RENDER_FOLLOW_UP_BATCH_SIZE,
        "follow-up batches must remain bounded"
    );
    rendered.push(...batch);
    offset += batch.length;
}

assert.deepEqual(rendered, icons, "progressive batches render every visible icon once in source order");
assert.equal(new Set(rendered.map((icon) => icon.name)).size, icons.length);
assert.equal(isActiveRenderGeneration(4, 4), true);
assert.equal(isActiveRenderGeneration(5, 4), false, "a new render generation cancels stale work");
assert.equal(
    isWithinRenderContinuationThreshold({ top: 1380, bottom: 1381 }, 900),
    true,
    "the continuation resumes while its sentinel is within the viewport margin"
);
assert.equal(
    isWithinRenderContinuationThreshold({ top: 1381, bottom: 1382 }, 900),
    false,
    "the continuation stops once its sentinel is outside the viewport margin"
);

let idleCallback;
let warmed = false;
const idleToken = scheduleDeferredIconCacheWarming(
    () => {
        warmed = true;
    },
    {
        requestIdleCallback: (callback, options) => {
            idleCallback = { callback, options };
            return "idle-token";
        },
        setTimeoutFn: () => {
            throw new Error("idle scheduling should be preferred when available");
        },
    }
);

assert.equal(idleToken, "idle-token");
assert.equal(warmed, false, "cache warming must not run in the startup task");
assert.equal(idleCallback.options.timeout, 1500);
idleCallback.callback();
assert.equal(warmed, true);

let timerCallback;
const timerToken = scheduleDeferredIconCacheWarming(
    () => {},
    {
        requestIdleCallback: undefined,
        setTimeoutFn: (callback, delay) => {
            timerCallback = callback;
            assert.equal(delay, 250, "legacy browsers defer cache warming with a short timer");
            return "timer-token";
        },
    }
);

assert.equal(timerToken, "timer-token");
assert.equal(typeof timerCallback, "function");

console.log("startup_rendering.test.js: ok");
