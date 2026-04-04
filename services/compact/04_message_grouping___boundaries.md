# Chapter 4: Message Grouping & Boundaries

In the previous chapter, [Conversation Summarization (Compaction)](03_conversation_summarization__compaction_.md), we learned how to take a long conversation and rewrite it into a concise summary.

But here is the catch: **You cannot just cut a conversation anywhere you want.**

If you cut the history at the wrong spot—like in the middle of a sentence or halfway through a complex task—you will confuse the AI and cause API errors. In this chapter, we will look at **Message Grouping**, the utility that ensures we only slice the conversation at "safe" points.

## The Motivation: The "Cut Wire" Problem

Imagine you are on a phone call.

1.  **You:** "Can you calculate 50 * 50?"
2.  **AI:** "Sure, let me use my calculator tool."
3.  *(...System prepares to run the tool...)*
4.  **Tool Output:** "2500"
5.  **AI:** "The answer is 2500."

Now, imagine the Auto-Compact system wakes up at step 3 because the memory is full. It decides to summarize everything up to that point and delete the recent messages.

If it cuts the history **between step 2 and step 4**, the AI wakes up with amnesia. It sees the "Tool Output: 2500" but has **zero memory** of asking for it. This causes a `dangling_tool_result` error, and the API crashes.

**Use Case:**
You are building an autonomous agent that performs multi-step coding tasks. It edits a file, runs a test, sees the error, fixes the file, and runs the test again. You need to summarize the history, but you must ensure you don't delete the "Run Test" command while keeping the "Test Result."

## Key Concepts

To prevent these crashes, we group messages into logical units called **API Rounds**.

1.  **The Atomic Unit:** A User Prompt, the Assistant's thought process, the Tool calls, and the Tool results are all considered **one unbreakable chain**. We treat them as a single block.
2.  **The Safe Boundary:** The only safe place to cut is *after* the Assistant has fully finished a turn and *before* the next User prompt begins.
3.  **The Tracker:** We use the unique ID of the Assistant message to tell when one turn ends and a new one begins.

## How It Works: Grouping by Round

We use a function called `groupMessagesByApiRound`. It takes a flat list of messages and returns a list of "groups."

### Example Input (Flat List)
```text
1. User: "Check the weather."
2. Assistant (ID: A1): "Using weather tool..."
3. Tool (ID: A1): "Sunny"
4. Assistant (ID: A1): "It is sunny."
5. User: "Great, thanks."
6. Assistant (ID: B2): "You're welcome."
```

### The Grouping Logic
The system groups these based on the interaction flow.

```typescript
const groups = groupMessagesByApiRound(allMessages);
```

### Example Output (Grouped)
The function returns an array of arrays. Notice how the Tool Call and Result stay together with the Assistant that requested them.

```text
Group 1:
  [User: "Check weather", Assistant: "Using tool...", Tool: "Sunny", Assistant: "It is sunny"]

Group 2:
  [User: "Great, thanks", Assistant: "You're welcome"]
```

## Internal Implementation: Under the Hood

How does the system know where to draw the line? It watches the **Assistant ID**.

When the AI replies, it generates a unique ID. If it calls a tool and then continues speaking, that ID usually remains consistent (or logically linked) for that "turn." If we see a *new* Assistant ID, we know a new round has started.

### The Logic Flow

```mermaid
sequenceDiagram
    participant Loop as Loop through Messages
    participant Current as Current Group
    participant Final as Final Groups List

    Loop->>Loop: Read Message 1 (User)
    Loop->>Current: Add to Current Group
    
    Loop->>Loop: Read Message 2 (Assistant ID: A1)
    Loop->>Current: Add to Current Group
    
    Loop->>Loop: Read Message 3 (Assistant ID: B2)
    Note over Loop: ID Changed! (A1 -> B2)
    Loop->>Final: Save "Current Group" (A1)
    Loop->>Current: Start NEW Group with Message 3
```

### The Code: `grouping.ts`

Let's look at the actual code that handles this. It is a simple loop with a "state" tracker.

First, we set up our containers.

```typescript
export function groupMessagesByApiRound(messages: Message[]): Message[][] {
  const groups: Message[][] = []
  let currentGroup: Message[] = []
  
  // We track the ID of the last assistant we saw
  let lastAssistantId: string | undefined

  // ... loop starts here
}
```
*Explanation: `groups` will hold our final result. `currentGroup` builds the specific chain we are currently looking at.*

Next, we iterate through every message. This is where the magic happens. We check if the Assistant ID has changed.

```typescript
  for (const msg of messages) {
    // Check if this is a NEW assistant turn
    const isNewTurn = msg.type === 'assistant' && 
                      msg.message.id !== lastAssistantId && 
                      currentGroup.length > 0

    if (isNewTurn) {
      // Seal the previous group and start a new one
      groups.push(currentGroup)
      currentGroup = [msg]
    } else {
      // Otherwise, keep adding to the current chain
      currentGroup.push(msg)
    }
```
*Explanation: If we see an Assistant message, and its ID is different from the last one we saw, we know the previous conversation "round" is finished. We save that group and start fresh.*

Finally, we update our tracker and handle the end of the loop.

```typescript
    // Update the tracker so we know for next time
    if (msg.type === 'assistant') {
      lastAssistantId = msg.message.id
    }
  }

  // Don't forget the very last group!
  if (currentGroup.length > 0) {
    groups.push(currentGroup)
  }
  
  return groups
}
```
*Explanation: We always update `lastAssistantId` so we can compare it against the next message. After the loop finishes, we push whatever is left in `currentGroup` to the final list.*

## Why This Matters for Compaction

Now that we have these groups, the **Compaction** engine (Chapter 3) becomes much safer.

Instead of saying "Delete messages 1 through 15," the engine can say "Delete **Groups** 1 through 3."

This ensures that we never accidentally delete a Tool Call while leaving the Tool Result dangling. We either keep the whole interaction, or we summarize the whole interaction.

## Summary

In this chapter, you learned:
1.  **Message Grouping** prevents "broken" conversation history that leads to API errors.
2.  An **API Round** is an atomic unit containing the user prompt, the AI's thought process, and any resulting tool usage.
3.  We identify boundaries by tracking the **Assistant ID**; when it changes, a new round begins.

Now we can group messages safely. But sometimes, even a single group is too large. What if the AI generated 500 lines of JSON data in one turn? We don't want to summarize the whole conversation, we just want to shrink that one massive message.

[Next Chapter: Micro-Compaction & Pruning](05_micro_compaction___pruning.md)

---

Generated by [Code IQ](https://github.com/adityasoni99/Code-IQ)