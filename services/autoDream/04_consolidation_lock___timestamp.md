# Chapter 4: Consolidation Lock & Timestamp

In the previous chapter, [Session Discovery](03_session_discovery.md), we learned how the system identifies which conversation files are new.

Now we face a critical safety challenge. What happens if you have two windows open, or two background processes running, and *both* decide it's time to organize memory at the exact same moment?

They would both try to read and write files simultaneously, leading to corrupted data or duplicate memories. To prevent this, we use a **Consolidation Lock**.

## The Problem: The "Double Cleaning" Disaster

Imagine an office cleaning crew.
1.  **Crew A** enters the room to organize the filing cabinet.
2.  **Crew B** enters 5 minutes later, while Crew A is still moving files.
3.  Crew B sees a file on a desk (which Crew A just put there) and moves it somewhere else.
4.  Result: Chaos. Files are lost or duplicated.

## The Solution: The Punch Card

To solve this, we use a single file named `.consolidate-lock`. It acts exactly like a punch card on the door of the office.

This single file serves **two** distinct purposes at the same time:

### 1. The Timestamp (When was the room cleaned?)
The **Last Modified Time** (`mtime`) of this file tells us when the last dream finished.
*   **Use Case:** The [Gating Logic](02_gating_logic.md) reads this timestamp to decide if 24 hours have passed.

### 2. The Lock (Is someone inside?)
The **Content** of this file stores the ID of the process (the "Cleaner") currently inside.
*   **Use Case:** If the file contains a valid Process ID (PID), other agents know to stay away.

## Visualizing the Logic

Here is the flow when an agent tries to start a dream:

```mermaid
flowchart TD
    Start([Start Dream]) --> CheckFile{Check .consolidate-lock}
    
    CheckFile -- File Exists & Valid PID --> Occupied[STOP: Room Occupied]
    CheckFile -- File Empty or Old PID --> Enter[Acquire Lock]
    
    Enter --> WritePID[Write My PID to File]
    WritePID --> Work[Do Memory Work...]
    
    Work -- Success --> Leave[Leave File (Update mtime)]
    Work -- Failure --> Reset[Reset mtime to Old Value]
```

## Internal Implementation

The code for this mechanism resides in `consolidationLock.ts`. Let's break it down into its core functions.

### 1. Checking the Timestamp

First, we need to know *when* the last consolidation happened. We don't need to read the file's content for this; we just ask the operating system for the file's statistics (`stat`).

```typescript
// From consolidationLock.ts
export async function readLastConsolidatedAt(): Promise<number> {
  try {
    // 'stat' gives us file metadata
    const s = await stat(lockPath())
    // Return the modification time in milliseconds
    return s.mtimeMs
  } catch {
    // If file doesn't exist, it has never run (return 0)
    return 0
  }
}
```
**Explanation:** This is a very "cheap" operation. It allows the **Time Gate** to run frequently without slowing down your computer.

### 2. Acquiring the Lock

This is the most critical part. When we decide to dream, we try to write our name (Process ID) into the file.

However, we must be careful not to overwrite someone else who is currently working.

```typescript
export async function tryAcquireConsolidationLock(): Promise<number | null> {
  const path = lockPath()

  // 1. Check if someone is already there
  try {
    const content = await readFile(path, 'utf8')
    const pid = parseInt(content)
    
    // If the process holding the lock is still alive...
    if (isProcessRunning(pid)) {
      return null // STOP! Do not enter.
    }
  } catch { /* File doesn't exist yet, safe to proceed */ }

  // ... continued below ...
```
**Explanation:** We read the file. If we find a number inside, and that number corresponds to a program currently running on your computer (`isProcessRunning`), we back off immediately.

If the coast is clear, we claim the room:

```typescript
  // 2. Claim the lock
  // Write OUR Process ID to the file
  await writeFile(path, String(process.pid))

  // 3. Double-check (Race Condition Protection)
  // Re-read the file to make sure someone didn't write over us instantly
  const verify = await readFile(path, 'utf8')
  
  // If the file doesn't have our ID, we lost the race.
  if (verify !== String(process.pid)) return null

  return mtimeMs // Success!
}
```
**Explanation:** Step 3 is vital. In the nanoseconds between checking the file and writing to it, another process might have jumped in. By reading it back, we ensure we actually won the "race."

### 3. Handling Failure (The Rollback)

What happens if the AI crashes *while* it is dreaming?

If we do nothing, the `.consolidate-lock` file will have a timestamp of "Now." The system will think: "Oh, we just finished cleaning!" and wait another 24 hours. But the cleaning was never finished!

To fix this, we use a **Rollback**. If the task fails, we manually reset the file's timestamp back to what it was *before* we started.

```typescript
export async function rollbackConsolidationLock(priorMtime: number): Promise<void> {
  const path = lockPath()
  
  // Clear the PID so others know the room is empty
  await writeFile(path, '')
  
  // Reset the clock! 
  // utimes allows us to manually set the modification time
  const t = priorMtime / 1000 
  await utimes(path, t, t)
}
```
**Explanation:** This is like a time machine. If the cleaning crew catches on fire halfway through, we magically reset the punch card to say the room hasn't been cleaned since last week. This ensures the next available crew will try again immediately.

## Why use one file for both?

You might wonder why we don't use two separate files: `last-run.txt` and `current-lock.txt`.

We use a single file for **Atomic Consistency**.
*   When the process finishes successfully, it simply stops.
*   The act of writing the PID updated the `mtime` automatically at the start.
*   This means the "Last Attempted" time is always perfectly synced with the lock creation. It keeps the filesystem operations minimal and robust.

## Conclusion

The **Consolidation Lock** is the safety guard of the Auto-Dream system.
1.  It uses `mtime` to tell the **Orchestrator** *when* to run.
2.  It uses `PID` content to ensure **Safety** so only one dream happens at a time.
3.  It supports **Rollbacks** to ensure failures don't count as success.

Now that we have successfully locked the room and are ready to work, what exactly do we tell the AI to do? We need to construct a specific set of instructions.

[Next Chapter: Dream Prompt Strategy](05_dream_prompt_strategy.md)

---

Generated by [Code IQ](https://github.com/adityasoni99/Code-IQ)