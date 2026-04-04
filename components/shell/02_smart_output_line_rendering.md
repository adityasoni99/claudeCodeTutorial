# Chapter 2: Smart Output Line Rendering

Welcome back! In the previous chapter, [Output Visibility Context](01_output_visibility_context.md), we learned how to tell the shell *when* to show full output versus when to truncate it to save space.

Now, we will focus on **how** that output actually looks.

## Motivation: The "Wall of Text" Problem

Terminals deal with raw text. Often, that text is ugly and hard to read.

Imagine your command returns a messy JSON object like this:
`{"status":"ok","data":{"id":123,"url":"https://example.com"}}`

**Without Smart Rendering:**
- It is a single, hard-to-read line.
- You can't click the URL.
- If it has weird formatting codes, it might look broken.

**With Smart Rendering:**
- It automatically expands into a readable, multi-line JSON structure.
- The URL becomes a clickable hyperlink.
- Broken styling is cleaned up.

We need a component that acts like a "pair of glasses" for our terminal—making everything crisp, clear, and interactive.

## Key Concepts

The **Smart Output Line** performs three specific "magic tricks" on every line of text before showing it to you:

1.  **The JSON Detective:** It looks at the text and asks, "Is this JSON?" If yes, it formats it with nice indentation.
2.  **The Linkifier:** It scans for text starting with `http://` or `https://` and turns it into a clickable link.
3.  **The Sanitizer:** It removes specific "underline" ANSI codes that are known to cause visual glitches in this specific shell environment.

## How to Use It

The main component is called `<OutputLine />`. You rarely need to configure it deeply; you just feed it text.

### Basic Usage

```tsx
import { OutputLine } from './OutputLine';

function MyCommandResult() {
  const rawData = '{"user": "Alice", "website": "https://alice.com"}';

  // The component automatically detects JSON and URLs
  return (
    <OutputLine 
      content={rawData} 
      linkifyUrls={true} 
    />
  );
}
```

**What happens here?**
Instead of one flat line, the user sees:
```json
{
  "user": "Alice",
  "website": "https://alice.com"
}
```
And `https://alice.com` will be clickable!

## Internal Implementation

How does this assembly line work? Let's look at the flow of data.

### High-Level Flow

When you pass a string to `<OutputLine />`, it goes through a pipeline of transformation functions.

```mermaid
sequenceDiagram
    participant Raw as Raw String
    participant JSON as JSON Detective
    participant Link as Linkifier
    participant View as Visibility Check
    participant Final as Screen

    Raw->>JSON: Looks like JSON?
    Note over JSON: Yes! Pretty-print it.
    JSON->>Link: Contains URL?
    Note over Link: Wrap in <Link>
    Link->>View: Should we truncate?
    Note over View: Check Chapter 1 Logic
    View->>Final: Render Clean Text
```

### Code Deep Dive

Let's look at the actual code logic in `OutputLine.tsx`. We will break it down into the three specific steps mentioned above.

#### Step 1: The JSON Detective
The shell attempts to parse every line. If it succeeds, it returns the "pretty" version. If it fails, it just returns the original text.

```tsx
// utils/slowOperations.js (Simplified)
export function tryFormatJson(line: string): string {
  try {
    const parsed = JSON.parse(line);
    // Return formatted JSON with 2-space indentation
    return JSON.stringify(parsed, null, 2);
  } catch {
    // If it crashes, it wasn't JSON. Return original.
    return line;
  }
}
```

**Explanation:** We use a simple `try/catch` block. This ensures that normal text (like "Hello World") doesn't break the shell; it simply skips the JSON formatting step.

#### Step 2: The Linkifier
Next, we scan for URLs.

```tsx
// OutputLine.tsx
const URL_REGEX = /https?:\/\/[^\s"'<>\\]+/g;

export function linkifyUrlsInText(content: string): string {
  // Replace plain text URLs with Hyperlink objects
  return content.replace(URL_REGEX, url => createHyperlink(url));
}
```

**Explanation:** This uses a Regular Expression (Regex) to find web addresses and wraps them in a helper that the terminal understands as a link.

#### Step 3: Putting it Together (The Render Loop)
The `OutputLine` component combines these steps with the logic we learned in [Output Visibility Context](01_output_visibility_context.md).

```tsx
// OutputLine.tsx
export function OutputLine({ content, verbose, linkifyUrls }) {
  // 1. Get the "Expand" signal from Chapter 1
  const expandShellOutput = useExpandShellOutput();
  const shouldShowFull = verbose || expandShellOutput;

  // 2. Run the formatting pipeline
  const formattedContent = useMemo(() => {
    let text = tryJsonFormatContent(content); // Step 1: JSON
    
    if (linkifyUrls) {
      text = linkifyUrlsInText(text);         // Step 2: Links
    }
    
    // Step 3: Decide to Truncate or Show All
    if (shouldShowFull) {
       return stripUnderlineAnsi(text);
    }
    // If not full, cut it short based on terminal width
    return renderTruncatedContent(text, columns); 

  }, [content, shouldShowFull, linkifyUrls]);

  return <Text>{formattedContent}</Text>;
}
```

**Explanation:**
1.  We check `useExpandShellOutput()` (from Chapter 1) to see if we are in "Full Attention" mode.
2.  We run `tryJsonFormatContent`.
3.  We run `linkifyUrlsInText`.
4.  Finally, we decide whether to show the whole thing or chop it off (`renderTruncatedContent`).

### The "Sanitizer" (Edge Case)

You might notice `stripUnderlineAnsi` in the code above.

```tsx
export function stripUnderlineAnsi(content: string): string {
  // Removes specific ANSI codes related to underlining
  return content.replace(/\u001b\[4m/g, ''); 
}
```

**Why?** Sometimes, raw output contains style codes that "leak." For example, if a line starts an underline but never finishes it, the rest of your terminal might stay underlined forever! This function acts as a safety net to prevent that visual bug.

## Summary

In this chapter, we explored **Smart Output Line Rendering**. We learned that:

1.  We can automatically detect and **pretty-print JSON** to make API results readable.
2.  We can convert text into **clickable links**.
3.  We combine these formatters with the **Output Visibility Context** to decide whether to show the full pretty result or a shortened version.

Now that we can display static text beautifully, what happens when a command is still running? How do we show spinners, timers, and progress bars?

[Next Chapter: Execution Progress Feedback](03_execution_progress_feedback.md)

---

Generated by [Code IQ](https://github.com/adityasoni99/Code-IQ)