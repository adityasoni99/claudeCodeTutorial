# Chapter 5: Security & Tokenization Sanitization

In [Chapter 4: Command Prefix Extraction](04_command_prefix_extraction.md), we learned how to identify *who* the command is (e.g., recognizing that `sudo git` is really just `git`).

Now we have a more dangerous problem: **Malicious Cargo.**

Just because we know the command is `git`, doesn't mean the arguments are safe. What if someone tries to trick the shell into running a second, hidden command? This chapter is about the **Security Guard** that inspects every piece of luggage (argument) to ensure it's safe.

## The Motivation: The "Trojan Horse" Attack

Shell commands are just text strings. This makes them flexible, but also vulnerable to **Injection Attacks**.

Imagine you want to create a file with a specific name.

**User Intention:**
`touch "important_file; rm -rf /"`

**The Danger:**
If our parser is "dumb," it sees the `;` and thinks:
1. Run `touch "important_file`
2. Run `rm -rf /` (Delete everything!)

We need a system that understands that because the semicolon is inside quotes (`""`), it is part of the filename, **not** a command separator.

## Key Concepts

### 1. Tokenization
Tokenization is the process of slicing a sentence into distinct words (tokens).
*   Input: `echo "Hello World"`
*   Bad Tokenization: `['echo', '"Hello', 'World"']` (Split by space)
*   Good Tokenization: `['echo', 'Hello World']` (Respects quotes)

### 2. Control Operators
These are the traffic lights of the shell. They tell the system when to stop one command and start another.
*   `;` (Sequence)
*   `&&` (And)
*   `||` (Or)
*   `|` (Pipe)

### 3. Sanitization (The Salt)
To safely parse commands, we sometimes need to hide dangerous characters temporarily. We replace them with unique, random codes (Salt) so our parser doesn't get confused, then put them back later.

## The Strategy: The Security Check

We use a process similar to airport security. We don't just let the bag through; we X-ray it.

1.  **Salt:** We generate random placeholders for quotes.
2.  **Hide:** We replace the quotes in the input string with these safe placeholders.
3.  **Parse:** We use a library to split the string.
4.  **Reveal:** We swap the placeholders back to the original characters.
5.  **Audit:** We check for mathematical balance (e.g., are there an even number of quotes?).

### The Flow

```mermaid
sequenceDiagram
    participant User as Raw Command
    participant Guard as Sanitizer
    participant Lib as Shell-Quote Lib
    participant Out as Safe Tokens

    User->>Guard: echo "Hello; World"
    Guard->>Guard: Generate Salt (e.g., __QT_123__)
    Guard->>Guard: Replace " with __QT_123__
    Guard->>Lib: Parse: echo __QT_123__Hello; World__QT_123__
    Note right of Lib: Lib sees no quotes, <br/>treats it as one big string!
    Lib-->>Guard: Tokens: ["echo", "__QT_123__Hello; World__QT_123__"]
    Guard->>Out: Restore: ["echo", "\"Hello; World\""]
```

## Implementation: Under the Hood

Let's look at `commands.ts` and `shellQuote.ts` to see how this works.

### Step 1: Generating the Salt

We need placeholders that a user could never guess. If we just used `__QUOTE__`, a hacker could type that manually to confuse us. We use `crypto` to make them unique.

```typescript
// From commands.ts
function generatePlaceholders() {
  // Generate 8 random bytes as hex
  const salt = randomBytes(8).toString('hex')
  
  return {
    // Example: __DOUBLE_QUOTE_a1b2c3d4__
    DOUBLE_QUOTE: `__DOUBLE_QUOTE_${salt}__`,
    SINGLE_QUOTE: `__SINGLE_QUOTE_${salt}__`,
    NEW_LINE: `__NEW_LINE_${salt}__`,
  }
}
```

*Explanation:* Every time we parse a command, we create a new secret language that only the system knows for that millisecond.

### Step 2: The Wrapper (Safety First)

We use a standard library called `shell-quote`, but it has known bugs. We wrap it in a `try/catch` block to ensure that if it crashes (due to malicious input), we don't crash the whole app.

```typescript
// From shellQuote.ts
export function tryParseShellCommand(cmd: string): ShellParseResult {
  try {
    // Attempt to parse using the library
    const tokens = shellQuoteParse(cmd)
    return { success: true, tokens }
  } catch (error) {
    // If it fails, log it and return failure safely
    return { 
      success: false, 
      error: error instanceof Error ? error.message : 'Unknown error' 
    }
  }
}
```

*Explanation:* This is our airbag. If the parsing library explodes, we catch the error gracefully.

### Step 3: Detecting Malformed Tokens

Here is where we catch the "Trojan Horse." Sometimes a parser might think a command is safe, but it actually has unbalanced quotes (e.g., `echo "hello`). This is often a sign of an attack or a mistake.

```typescript
// From shellQuote.ts
export function hasMalformedTokens(command: string, parsed: any[]): boolean {
  // 1. Manually count quotes in the raw text
  let doubleCount = 0
  for (const char of command) {
    if (char === '"') doubleCount++
  }

  // 2. If odd number of quotes, it's dangerous/malformed
  if (doubleCount % 2 !== 0) return true

  // 3. Check individual tokens for unbalanced braces {}
  for (const entry of parsed) {
    // ... logic to check { } balance inside tokens
  }
  
  return false
}
```

*Explanation:* We trust, but verify. Even if the parser gives us tokens, we do a sanity check. If you opened a quote but never closed it, we flag it as malformed.

### Step 4: Splitting with Operators

Finally, we put it all together in `splitCommandWithOperators`. This function takes a long string and returns a clean array of commands and operators.

```typescript
// From commands.ts (Simplified)
export function splitCommandWithOperators(command: string): string[] {
  const placeholders = generatePlaceholders()

  // 1. Swap unsafe chars for safe placeholders
  const safeCommand = command
    .replaceAll('"', `"${placeholders.DOUBLE_QUOTE}`)
    .replaceAll("'", `'${placeholders.SINGLE_QUOTE}`)

  // 2. Parse
  const result = tryParseShellCommand(safeCommand)
  
  // 3. Restore the original characters
  return result.tokens.map(token => {
    return token.replaceAll(placeholders.DOUBLE_QUOTE, '"')
  })
}
```

*Explanation:* This is the core workflow. We Armor the string -> Process it -> De-Armor it. This ensures that a semicolon inside a filename stays inside the filename.

## Handling Windows Quirks

Sometimes, operating systems behave differently. A common issue is how Windows handles output redirection to "nothing" (NULL).

*   Linux/Mac: `/dev/null`
*   Windows: `NUL`

If our AI hallucinates and tries to use Windows syntax on a Linux machine, it creates a file named "nul", which is very hard to delete! We rewrite this automatically.

```typescript
// From shellQuoting.ts
const NUL_REDIRECT_REGEX = /(\d?&?>+\s*)[Nn][Uu][Ll]/g

export function rewriteWindowsNullRedirect(command: string): string {
  // If we see "> nul", force it to become "> /dev/null"
  return command.replace(NUL_REDIRECT_REGEX, '$1/dev/null')
}
```

*Explanation:* This simple regex fixes a common cross-platform annoyance, preventing junk files from cluttering the user's workspace.

## Summary

In this chapter, we learned:

1.  **Injection Attacks:** How special characters can trick a shell into running malicious code.
2.  **Salted Placeholders:** How to hide dangerous characters during parsing using random strings.
3.  **Sanitization:** The process of ensuring tokens are balanced and safe.
4.  **Wrapper Pattern:** Encapsulating external libraries (`shell-quote`) to handle their failures safely.

We can now look at a command like `git commit -m "Fixed; broken stuff"` and confidently say: *"This is one command, and the semicolon is just text."*

However, there is one type of string that is even harder to parse than quotes: **Heredocs**. These are multi-line strings that use custom delimiters.

[Next Chapter: Heredoc Extraction & Restoration](06_heredoc_extraction___restoration.md)

---

Generated by [Code IQ](https://github.com/adityasoni99/Code-IQ)