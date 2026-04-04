# Chapter 5: Text Glimmer Effects

Welcome back! In the previous chapter, [Isolated Animation Loop](04_isolated_animation_loop.md), we built a high-performance engine that ticks 20 times a second.

Currently, that engine is just spinning a small character (`⠋`). The actual text next to it (e.g., "generating code...") is static. It sits there, unmoving.

To make our AI feel truly "alive" and "intelligent," we want to send a wave of light through the text, similar to the "Slide to Unlock" animation on old iPhones or the "Skeleton Loaders" on modern websites.

## Motivation: The "Flashlight" Effect

Imagine you are in a long, dark tunnel. On the wall, the words "THINKING..." are painted. If you stand still, it looks flat. But if you walk past it holding a flashlight, the letters light up one by one as you pass, then fade back into the dark.

This "passing light" tells the user:
1.  **The system is active:** The light is moving.
2.  **The text is readable:** We aren't changing the letters, just their brightness.

In **Spinner**, this is called the **Glimmer Effect**.

## Key Concepts

To achieve this, we need to master three concepts:

1.  **The Glimmer Index:** This is a number representing "where the flashlight is." If the index is 0, the first letter shines. If it's 5, the fifth letter shines.
2.  **The Shimmer Color:** We have a base color (e.g., Purple for "doing") and a highlight color (e.g., White).
3.  **Graphemes (The Emoji Trap):** Computers are bad at counting. They often think an emoji like 👨‍👩‍👧‍👦 is 7 different characters. If we light them up one by one, the emoji will break apart. We need to treat it as one "Grapheme."

## How to Use It

We use the component `GlimmerMessage`. We hook it up to the animation loop we built in Chapter 4.

The parent component calculates the `glimmerIndex` (which increases over time) and passes it down.

```tsx
<GlimmerMessage
  // The text to display
  message="translating to python..."
  
  // The spotlight position (calculated by our loop)
  glimmerIndex={frame % 30}
  
  // Base color (Darker)
  messageColor="processing"
  
  // Highlight color (Brighter)
  shimmerColor="processingLight"
/>
```

**What happens here?**
*   **Frame 0:** The "t" is bright.
*   **Frame 1:** The "r" is bright.
*   **Frame 2:** The "a" is bright.
*   ...and so on, creating a wave effect.

## Implementation Walkthrough

How does the component know which parts to paint? It cuts the string into three pieces every time it renders.

1.  **Before:** The text *behind* the flashlight (Base Color).
2.  **Shimmer:** The text *under* the flashlight (Highlight Color).
3.  **After:** The text *ahead* of the flashlight (Base Color).

```mermaid
sequenceDiagram
    participant Loop as Animation Loop
    participant GM as GlimmerMessage
    participant Split as Text Splitter

    Loop->>GM: Render with glimmerIndex = 3
    GM->>Split: "Thinking..."
    
    Split->>GM: Returns 3 parts
    Note right of Split: 1. "Thi" (Before)<br/>2. "n" (Shimmer)<br/>3. "king..." (After)
    
    GM->>GM: Color Part 1: Purple
    GM->>GM: Color Part 2: White
    GM->>GM: Color Part 3: Purple
```

## Implementation Deep Dive

Let's look at the code in `GlimmerMessage.tsx`.

### Step 1: Solving the Emoji Trap

Standard JavaScript strings split weirdly with emojis. We use `Intl.Segmenter` (a browser/Node standard) to split text by visual characters, not computer bytes.

```tsx
// Inside GlimmerMessage.tsx
// We do this ONCE when the message changes, not every frame.
const { segments } = React.useMemo(() => {
  const segs = [];
  // This magic tool respects emojis!
  for (const { segment } of getGraphemeSegmenter().segment(message)) {
    segs.push({ segment, width: stringWidth(segment) });
  }
  return { segments: segs };
}, [message]);
```

> **Beginner Tip:** `useMemo` is a React hook that caches the result. Splitting a string is expensive. We don't want to do it 20 times a second if the text hasn't changed!

### Step 2: The Three Buckets

Now that we have our safe list of characters (`segments`), we loop through them and sort them into our three buckets based on the `glimmerIndex`.

```tsx
let before = '';
let shim = '';
let after = '';
let colPos = 0;

for (const { segment, width } of segments) {
  // Is this character BEFORE the spotlight?
  if (colPos + width <= glimmerIndex) {
    before += segment;
  } 
  // Is this character AFTER the spotlight?
  else if (colPos > glimmerIndex + 1) {
    after += segment;
  } 
  // Then it must be UNDER the spotlight!
  else {
    shim += segment;
  }
  colPos += width;
}
```

### Step 3: Rendering the Buckets

Finally, we simply render the three strings side-by-side with different colors.

```tsx
return (
  <>
    {/* Part 1: Darker */}
    <Text color={messageColor}>{before}</Text>
    
    {/* Part 2: Brighter (The Flashlight!) */}
    <Text color={shimmerColor}>{shim}</Text>
    
    {/* Part 3: Darker */}
    <Text color={messageColor}>{after}</Text>
    {/* Add a trailing space to prevent layout jumps */}
    <Text color={messageColor}> </Text>
  </>
);
```

## Special Mode: Tool Use

Sometimes, the AI isn't just "thinking"; it is "using a tool" (like searching the web). When this happens, we want the text to flash entirely, pulsing like a heartbeat, rather than a wave passing through.

The `GlimmerMessage` component handles this by checking the `mode` prop.

```tsx
if (mode === 'tool-use') {
  // Interpolate between base color and shimmer color
  // based on a pulsing 'flashOpacity' (0 to 1)
  const interpolated = interpolateColor(
     baseRGB, 
     shimmerRGB, 
     flashOpacity
  );

  return <Text color={toRGBColor(interpolated)}>{message}</Text>;
}
```

## Conclusion

We have successfully added a professional polish to our UI.
1.  We use **Grapheme Segmentation** to keep emojis safe.
2.  We use **Bucket Sorting** (Before/Shimmer/After) to apply colors efficiently.
3.  We created a visual language: **Waves** mean thinking, **Pulses** mean tool usage.

But what happens if the "Thinking..." animation runs for 5 minutes? The user might think the AI has crashed. We need a way to detect if the agent has stopped responding and warn the user visually.

In the final chapter, we will build the safety system.

[Next Chapter: Stall Detection (Heartbeat)](06_stall_detection__heartbeat_.md)

---

Generated by [Code IQ](https://github.com/adityasoni99/Code-IQ)