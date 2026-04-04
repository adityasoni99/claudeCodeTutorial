# Chapter 4: Secret Scanning Engine

Welcome to the final chapter of the **Team Memory Sync** tutorial!

In the previous chapter, [Write Protection Guard](03_write_protection_guard.md), we built a "Bouncer" that stands at the door of our shared folder. It stops files from entering if they are dangerous.

But how does the Bouncer actually *know* if a file is dangerous? It doesn't use magic; it uses a specialized tool called the **Secret Scanning Engine**.

### The Problem: Finding a Needle in a Haystack

Imagine you have a text file with 1,000 lines of code. Hidden somewhere in there is a "GitHub Personal Access Token" that looks like this: `ghp_A1b2C3d4...`.

If we just search for the word "password", we will miss it.
If we search for "ghp", we might accidentally flag a variable named `highpower`.

We need a way to describe the **shape** of a secret without knowing the exact letters.

### The Solution: Regular Expressions (The "Wanted" Posters)

The Secret Scanning Engine relies on **Regular Expressions** (Regex). Think of a Regex as a "Wanted Poster" that describes a suspect's features rather than their name.

*   **Name Search:** "Find John Smith."
*   **Regex Search:** "Find a word that starts with 'sk-', followed by 20 random letters, ending with 'AA'."

We use a curated list of these patterns (sourced from the industry-standard tool `gitleaks`) to catch secrets like:
*   AWS Keys
*   OpenAI Keys
*   Slack Tokens
*   Private Keys

---

### Key Concept: The Rule Structure

Before we scan anything, we need to define what we are looking for. In our code, each secret is defined as a `SecretRule`.

Each rule has an **ID** (computer name) and a **Source** (the Regex pattern).

```typescript
// From: secretScanner.ts

type SecretRule = {
  id: string      // e.g., 'aws-access-token'
  source: string  // The Regex pattern
  flags?: string  // Options like 'case-insensitive'
}
```

---

### Step 1: The "Don't Catch Yourself" Trick

One funny problem with writing a secret scanner is that if you write the pattern for an API key in your code, the scanner might flag **itself** as a security risk!

For example, Anthropic keys start with `sk-ant-api`. If we write that string literally, the scanner sees it and panics. We solve this by breaking the string apart.

```typescript
// From: secretScanner.ts

// We assemble the prefix at runtime. 
// The scanner won't see "sk-ant-api" in this source code file.
const ANT_KEY_PFX = ['sk', 'ant', 'api'].join('-')
```
**Explanation:**  
We trick the system. To the computer reading the raw file, it sees three separate words. But when the program *runs*, it joins them into the dangerous prefix we need to search for.

---

### Step 2: Defining the Rules

We keep a list of high-confidence rules. We only use rules that are very specific to avoid false alarms.

Here is a simplified look at our list:

```typescript
// From: secretScanner.ts

const SECRET_RULES: SecretRule[] = [
  {
    id: 'aws-access-token',
    // Looks for specific AWS prefixes like AKIA, ASIA followed by 16 chars
    source: '\\b((?:A3T[A-Z0-9]|AKIA|ASIA)[A-Z2-7]{16})\\b',
  },
  {
    id: 'github-pat',
    // Looks for "ghp_" followed by 36 alphanumeric characters
    source: 'ghp_[0-9a-zA-Z]{36}',
  },
  // ... many more rules ...
]
```
**Explanation:**  
*   `\\b`: This means "Word Boundary." It ensures we don't match letters inside another word.
*   `[A-Z2-7]{16}`: This means "Find exactly 16 characters that are uppercase letters or numbers 2-7."

---

### Step 3: Lazy Compilation (Performance)

Regex patterns can be heavy to process. We don't want to prepare all these complex mathematical patterns if the user never actually saves a file to the team memory.

We use a technique called **Lazy Compilation**. We leave the rules as simple text strings until the very first time we need to scan something.

```typescript
// From: secretScanner.ts

let compiledRules: Array<{ id: string; re: RegExp }> | null = null

function getCompiledRules() {
  // If we haven't compiled yet, do it now!
  if (compiledRules === null) {
    compiledRules = SECRET_RULES.map(r => ({
      id: r.id,
      re: new RegExp(r.source, r.flags), // Convert string to executable logic
    }))
  }
  return compiledRules
}
```
**Explanation:**  
Think of this like assembling a metal detector. We keep the parts in a box (`SECRET_RULES`). We only bolt them together (`new RegExp`) when a customer actually walks through the door.

---

### Step 4: The Scan Workflow

Now, let's see how the engine actually processes text.

```mermaid
sequenceDiagram
    participant Guard
    participant Scanner as Secret Scanner
    participant Rules as Regex Engine

    Guard->>Scanner: scanForSecrets("My key is ghp_ABC...")
    
    loop Every Rule
        Scanner->>Rules: Does text match Rule X?
        alt Match Found
            Rules-->>Scanner: Yes! (It's a GitHub Key)
            Scanner->>Scanner: Add to report
        else No Match
            Rules-->>Scanner: No.
        end
    end
    
    Scanner->>Guard: Return List of Matches
```

---

### Step 5: Running the Scan

The main function `scanForSecrets` loops through every rule against your text.

```typescript
// From: secretScanner.ts

export function scanForSecrets(content: string): SecretMatch[] {
  const matches: SecretMatch[] = []
  const seen = new Set<string>() // To avoid listing the same error twice

  for (const rule of getCompiledRules()) {
    if (rule.re.test(content)) {
       // We found one!
       seen.add(rule.id)
       matches.push({ ruleId: rule.id, label: ruleIdToLabel(rule.id) })
    }
  }
  return matches
}
```

**Usage Example:**

```typescript
const text = "Use this for AWS: AKIAIOSFODNN7EXAMPLE"
const result = scanForSecrets(text)

console.log(result)
// Output: 
// [ 
//   { ruleId: 'aws-access-token', label: 'AWS Access Token' } 
// ]
```

**Explanation:**
1.  We get the "assembled" metal detectors (`getCompiledRules`).
2.  We run `.test(content)` for every rule.
3.  If it returns `true`, we add a readable label (like "AWS Access Token") to our list.
4.  We return the list to the Guard.

---

### Bonus: Safe Error Messages (Redaction)

If we catch a user pasting a secret, we want to warn them. But we shouldn't print the secret itself in our error logs! If we log the secret, we have just created a security leak in our own logs.

We have a helper function called `redactSecrets`.

```typescript
// From: secretScanner.ts

export function redactSecrets(content: string): string {
  // Loop through rules and replace matches with [REDACTED]
  for (const re of redactRules) {
    content = content.replace(re, '[REDACTED]')
  }
  return content
}
```

**Example:**
*   **Input:** `"My key is ghp_12345"`
*   **Output:** `"My key is [REDACTED]"`

This allows us to safely tell the user "You have a secret in line 5" without repeating the secret.

---

### Conclusion

Congratulations! You have completed the **Team Memory Sync** tutorial series.

You have built a sophisticated security system:
1.  **Chapter 1:** You built a [Lifecycle Manager](01_sync_lifecycle___error_suppression.md) that knows when to stop if things break.
2.  **Chapter 2:** You built a [File Watcher](02_team_memory_file_watcher.md) that efficiently batches updates.
3.  **Chapter 3:** You built a [Write Protection Guard](03_write_protection_guard.md) to intercept dangerous files.
4.  **Chapter 4:** You built the **Secret Scanning Engine** using Regex to identify those dangers.

With these four components working together, your team can share knowledge and memories with AI agents safely, securely, and efficiently.

**End of Tutorial.**

---

Generated by [Code IQ](https://github.com/adityasoni99/Code-IQ)