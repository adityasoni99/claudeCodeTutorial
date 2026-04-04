# Chapter 2: Content Fetching & Conversion

In the previous chapter, [WebFetchTool Definition](01_webfetchtool_definition.md), we built the "steering wheel" of our tool. We defined how the AI asks for a website.

But a steering wheel is useless without an engine. Now, we need to build the machinery that actually connects to the internet, downloads the data, and makes it readable.

## The Motivation: The "Translator" Analogy

Websites are written in **HTML** (HyperText Markup Language). HTML is full of tags like `<div>`, `<script>`, and `<style>` that control layout and colors.

If we feed raw HTML to an AI, it wastes "tokens" (memory) on code that doesn't matter. The AI just wants the text.

**The Solution:**
We need a **Fetcher & Converter** engine. Think of this engine like a **Translator**:
1.  **Goes to the library** (The Internet).
2.  **Finds the book** (The URL).
3.  **Translates it** from complex HTML to simple Markdown.
4.  **Hands it back** to the AI.

## The Main Function: `getURLMarkdownContent`

The core of this chapter is a function located in `utils.ts` called `getURLMarkdownContent`. This is the workhorse of our tool.

Here is the high-level strategy for this function:

1.  **Validate:** Is this a real URL? Is it safe?
2.  **Upgrade:** Change `http` (insecure) to `https` (secure).
3.  **Fetch:** Download the data (handling redirects carefully).
4.  **Convert:** Use a library called `turndown` to turn HTML into Markdown.

Let's break down each step.

### Step 1: Validation and Upgrading

Before we make a network request, we need to ensure the URL is valid and secure.

```typescript
// utils.ts
export async function getURLMarkdownContent(url, abortController) {
  // 1. Basic Validation
  if (!validateURL(url)) {
    throw new Error('Invalid URL')
  }

  // 2. Upgrade HTTP to HTTPS automatically
  let parsedUrl = new URL(url)
  if (parsedUrl.protocol === 'http:') {
    parsedUrl.protocol = 'https:'
  }
  const upgradedUrl = parsedUrl.toString()
  
  // ... continued below
}
```

*   **`validateURL`**: This helper checks if the URL is well-formed. It also ensures there are no usernames or passwords hidden in the URL (e.g., `http://user:pass@example.com`), which is a security risk.
*   **HTTPS Upgrade**: We always try to use the secure version of a site. It's like putting on a seatbelt before driving.

### Step 2: The Enterprise "Preflight" Check

In some corporate environments, computers aren't allowed to visit just *any* website. We perform a quick check against a blocklist.

```typescript
  // Check if the domain is allowed by enterprise rules
  const hostname = parsedUrl.hostname
  const checkResult = await checkDomainBlocklist(hostname)
  
  if (checkResult.status === 'blocked') {
    throw new DomainBlockedError(hostname)
  }
```

This prevents the tool from accidentally visiting sites that the user's organization has explicitly banned.

### Step 3: Fetching (and Chasing Redirects)

This is the tricky part. Sometimes you visit `example.com`, but the server says, "I moved! Go to `www.example.com`." This is called a **Redirect**.

However, we can't blindly follow every redirect. A bad actor could redirect us to a malicious internal server. We use a custom fetcher called `getWithPermittedRedirects`.

```typescript
  // Download the raw data
  const response = await getWithPermittedRedirects(
    upgradedUrl, 
    abortController.signal, 
    isPermittedRedirect // Our safety rule
  )

  // If it's still a redirect (e.g., to a different website), stop here.
  if (response.type === 'redirect') {
    return response
  }
```

**Why do we return redirects instead of following them?**
If `example.com` redirects to `google.com`, that's a completely different website! We stop and ask the AI (and the user) for permission again. We only auto-follow "safe" redirects (like adding `www`).

### Step 4: The Conversion (HTML -> Markdown)

Once we have the raw data (the HTML), we need to clean it up. We use a library called `turndown`.

```typescript
  const rawBuffer = Buffer.from(response.data)
  const htmlContent = rawBuffer.toString('utf-8')
  
  // Use 'turndown' library to convert HTML to Markdown
  const turndownService = await getTurndownService()
  const markdownContent = turndownService.turndown(htmlContent)

  return {
    content: markdownContent,
    bytes: rawBuffer.length,
    code: response.status
  }
```

Now, instead of `<h1 class="bold">Hello</h1>`, the AI receives `# Hello`. This is much easier to read and cheaper to process.

## Visualizing the Flow

Here is what happens inside the engine when we request a page:

```mermaid
sequenceDiagram
    participant Tool as WebFetchTool
    participant Validator as Validation
    participant Web as Internet
    participant Convert as Turndown Lib

    Tool->>Validator: Is URL safe?
    Validator-->>Tool: Yes
    
    Tool->>Web: HTTP GET (Secure)
    
    alt Redirects (e.g. add www)
        Web-->>Tool: 301 Moved -> Follow it
        Tool->>Web: GET New URL
    end

    Web-->>Tool: 200 OK (Raw HTML)
    Tool->>Convert: Convert HTML to Markdown
    Convert-->>Tool: Clean Markdown text
    Tool->>Tool: Return Content
```

## Deep Dive: Safe Redirects

Security is a major theme in this project. Let's look at `isPermittedRedirect`. This function decides if we should follow a "Moved" sign automatically.

```typescript
export function isPermittedRedirect(original, redirect) {
  const url1 = new URL(original)
  const url2 = new URL(redirect)

  // Remove "www." from both to compare them
  const host1 = url1.hostname.replace(/^www\./, '')
  const host2 = url2.hostname.replace(/^www\./, '')

  // Only allow if the base domain is the same!
  return host1 === host2
}
```

*   **Allowed:** `http://example.com` -> `https://www.example.com` (Same site, just secure/www).
*   **Blocked:** `http://example.com` -> `http://evil-site.com` (Different site).

If the redirect is blocked, the tool stops and tells the AI: "This site redirects to somewhere else. Do you want to go there?"

## Caching (Brief Intro)

To make things faster, we don't fetch the same page twice in a row.

```typescript
  // Check the cache first!
  const cachedEntry = URL_CACHE.get(url)
  if (cachedEntry) {
    return cachedEntry
  }
```

We use a simple LRU (Least Recently Used) cache. If we fetched the page 2 minutes ago, we just return the saved result. We will cover this in detail in [Response Caching](06_response_caching.md).

## What about PDFs?

Sometimes a URL points to a PDF, not an HTML page. The `WebFetchTool` handles this too.

```typescript
  if (isBinaryContentType(contentType)) {
    // Save the raw file to disk so Claude can read it later
    const result = await persistBinaryContent(rawBuffer, contentType)
    persistedPath = result.filepath
  }
```

Ideally, we try to extract text from PDFs, but we also save the file so the AI can use other tools to read it if the text extraction fails.

## Conclusion

We have successfully built the engine!

1.  We verify the URL is safe.
2.  We upgrade to HTTPS.
3.  We follow safe redirects only.
4.  We convert messy HTML into clean Markdown.

**But we have a problem.**
Some websites are huge. A single page might be 50,000 words long. If we send all that text to the AI, it might get confused or run out of memory.

In the next chapter, we will learn how to take this clean Markdown and use a secondary, smaller AI model to extract *only* what we need.

[Next: AI Content Extraction](03_ai_content_extraction.md)

---

Generated by [Code IQ](https://github.com/adityasoni99/Code-IQ)