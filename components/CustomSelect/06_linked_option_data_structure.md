# Chapter 6: Linked Option Data Structure

Welcome to the final chapter of our series!

In the previous chapter, [Chapter 5: Navigation Engine & Viewport](05_navigation_engine___viewport.md), we built a powerful engine that calculates which items are visible on the screen. We mentioned that the engine needs to find the "next" or "previous" item instantly to handle scrolling.

But we glossed over *how* it finds that neighbor. Does it search through the entire array every time you press a key? That would be slow.

In this chapter, we will build the **Linked Option Data Structure** (specifically, the `OptionMap` class). This is the secret weapon that makes our navigation lightning fast, even with thousands of items.

## Motivation: The "Rolodex" Problem

Imagine you have a list of 10,000 songs.
You are currently playing Song #500 (`id: "song_500"`). The user presses the "Down Arrow" to play the next song.

### The Array Approach (The Slow Way)
If you keep your data in a standard array, the computer has to do this:
1.  Start at the beginning.
2.  "Is this song_500? No."
3.  "Is this song_500? No."
4.  ... 499 checks later ...
5.  "Found it! Okay, now give me the one at index + 1."

This is called **O(N)** complexity. As your list grows, your app gets slower.

### The Linked List Approach (The Fast Way)
Now imagine a physical **Rolodex**. When you are looking at a card, you don't need to search the whole pile to find the next one. You just flip the card. The current card is physically touching the next one.

This is **O(1)** complexity. It takes the same amount of time whether you have 10 songs or 10 million.

## Core Concept: `OptionMap`

The `OptionMap` is a specialized data structure that combines two powerful concepts:

1.  **A Map (Lookup):** Like a dictionary. You give it an ID ("pepperoni"), and it instantly gives you the object.
2.  **A Doubly Linked List:** Every object knows exactly who is before it and who is after it.

### The Structure

Instead of a simple object like `{ value: 'a' }`, our data looks like this inside the map:

```typescript
// A single item in our chain
{
  value: 'pepperoni',
  // ...
  previous: { /* Link to Mushroom */ },
  next:     { /* Link to Onion */ }
}
```

## Use Case: Instant Navigation

Here is how the Navigation Engine (from Chapter 5) uses this structure.

### Scenario
The user is focused on "Pepperoni" and presses the Down Arrow.

### Code Example

```typescript
// 1. Get the current item instantly using the Map feature
const currentItem = optionMap.get('pepperoni');

// 2. Get the next item instantly using the Linked List feature
const nextItem = currentItem.next;

// 3. That's it! We have the data.
console.log(`Moving to: ${nextItem.label}`);
```

No searching. No looping. Just instant movement.

## Internal Implementation: How it Works

How do we turn a flat array (from the user) into this rich, linked structure? We do it once when the component initializes.

### The Assembly Line

We loop through the array one time. As we pick up each item, we introduce it to the previous item we held.

```mermaid
sequenceDiagram
    participant Array as Input List
    participant Loop as The Builder
    participant Prev as Previous Item
    participant Curr as Current Item

    Array->>Loop: Give me Item B
    Loop->>Curr: Create Node for B
    
    Note over Loop, Prev: Link them together!
    
    Loop->>Prev: Set "Next" = B
    Loop->>Curr: Set "Previous" = A
    
    Note over Loop, Curr: Move forward
    Loop->>Loop: Previous becomes B
```

### Code Walkthrough: `option-map.ts`

Let's look at the implementation. This class extends the JavaScript built-in `Map`, adding our linking logic.

#### 1. The Container

First, we define what a "Node" looks like. It holds the data plus the `next` and `previous` pointers.

```typescript
// option-map.ts

// The shape of our smart objects
type OptionMapItem<T> = {
  label: ReactNode
  value: T
  // The links to neighbors
  previous: OptionMapItem<T> | undefined
  next: OptionMapItem<T> | undefined
  index: number
}
```

#### 2. The Setup

The class accepts the plain array of options in its constructor. We prepare some variables to keep track of the chain.

```typescript
export default class OptionMap<T> extends Map<T, OptionMapItem<T>> {
  
  constructor(options: OptionWithDescription<T>[]) {
    // We will store the pairs here before creating the Map
    const items: Array<[T, OptionMapItem<T>]> = []
    
    // We need to remember the item we just processed
    let previous: OptionMapItem<T> | undefined
    
    // ... loop starts below ...
```

#### 3. The Loop and Link

This is the most important part. We iterate over the user's options. For each one, we connect it to the `previous` one.

```typescript
    for (const option of options) {
      // 1. Create the new smart node
      const item = {
        value: option.value,
        previous: previous, // "My left hand holds the previous guy"
        next: undefined,    // We don't know the next guy yet
        // ... other props
      }

      // 2. If there was a previous item, introduce them!
      if (previous) {
        previous.next = item; // "Previous guy, meet your new neighbor"
      }
```

#### 4. Updating State

Finally, we update our trackers so the loop can continue, and then we finalize the Map.

```typescript
      // 3. Add to our list of pairs for the Map
      items.push([option.value, item]);

      // 4. This item is now the "previous" for the next loop iteration
      previous = item;
    }

    // 5. Initialize the Map capabilities
    super(items);
  }
}
```

## Why This Matters for Beginners

You might ask, *"Is this overkill? Why not just use `array[index + 1]`?"*

For a list of 5 items? Yes, it is overkill.
But `CustomSelect` is designed to be a professional-grade component.

1.  **Performance:** It handles 10,000 items as smoothly as 10 items.
2.  **Code Clarity:** In [Chapter 5: Navigation Engine & Viewport](05_navigation_engine___viewport.md), our logic was simply `currentItem.next`. We didn't have to write messy math like `array[i + 1]` or handle "index out of bounds" errors manually every time. The data structure handled the complexity for us.

## Series Conclusion

Congratulations! You have navigated through the entire architecture of the **CustomSelect** project.

Let's recap our journey:

1.  **[Chapter 1](01_multi_select_container.md):** We built the **Container** ("The Boss") to orchestrate the flow.
2.  **[Chapter 2](02_option_renderers.md):** We created **Renderers** ("The Painters") to draw text and inputs.
3.  **[Chapter 3](03_selection_behavior_hooks.md):** We defined **Hooks** ("The Rulebook") for how selection works.
4.  **[Chapter 4](04_input_controller.md):** We added an **Input Controller** ("The Driver") to handle keyboards.
5.  **[Chapter 5](05_navigation_engine___viewport.md):** We implemented a **Navigation Engine** ("The Camera") to handle scrolling.
6.  **Chapter 6 (This Chapter):** We optimized it all with a **Linked Data Structure** ("The Rolodex").

You now understand how to build a complex, performant, and interactive CLI component from scratch. Happy coding!

---

Generated by [Code IQ](https://github.com/adityasoni99/Code-IQ)