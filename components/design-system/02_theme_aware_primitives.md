# Chapter 2: Theme-Aware Primitives

Welcome back! In the previous chapter, [Theming Context & Utilities](01_theming_context___utilities.md), we built the "brain" of our application—a central nervous system that knows whether we are in Dark Mode or Light Mode.

However, a brain without a body can't do much. Now, we need to build the basic building blocks—the "atoms"—of our interface: **Text** and **Boxes**.

## The Motivation

Imagine you are building a CLI tool. You want error messages to be red. You *could* write this everywhere:

```tsx
<Text color="#FF0000">Error: File not found</Text>
```

**The Problem:**
1.  **Hard to maintain:** If you decide errors should be a softer pink later, you have to find and replace that hex code in 50 different files.
2.  **No Dark Mode:** `#FF0000` might look great on a black background, but terrible on a white background.

**The Solution:**
We create **Theme-Aware Primitives**. Instead of asking for "Red," we ask for "Error."

We tell the component *what the text means* (Semantics), not *what it looks like* (Style). The component then asks the Theme Provider: "Hey, what color is 'Error' right now?"

## Use Case: The "Success" Message

Let's say we want to display a message saying "Deployment Finished."

**The Old Way (Hardcoded):**
You have to manually pick colors that look good.

**The New Way (Theme-Aware):**
We use our new wrappers: `ThemedText` and `ThemedBox`.

```tsx
<ThemedBox borderColor="success" borderStyle="round">
  <ThemedText color="success">Deployment Finished</ThemedText>
</ThemedBox>
```

If the user is in Dark Mode, this might render as **Bright Green**. If they switch to Light Mode, it might automatically switch to **Dark Green** to remain readable. You don't have to change a single line of code.

## Key Concept: Semantic Keys

Instead of passing CSS values (like `blue`, `red`, `#333`), we pass **Theme Keys**. These are names that describe the *purpose* of the color.

Common keys in our system include:
*   `primary`: The main brand color.
*   `success`: Usually green.
*   `warning`: Usually yellow/orange.
*   `error`: Usually red.
*   `surface`: The background color of panels.

## How to Use `ThemedText`

`ThemedText` is a wrapper around Ink's standard `<Text>` component.

### Basic Usage

```tsx
import { ThemedText } from './design-system';

// Uses the theme's 'primary' color
<ThemedText color="primary">
  Hello World
</ThemedText>
```

### Background Colors

You can also set the background color using theme keys.

```tsx
// White text on a Red background (assuming 'error' is red)
<ThemedText color="surface" backgroundColor="error">
  CRITICAL FAILURE
</ThemedText>
```

**What happens here?**
The component looks up `surface` (e.g., #FFFFFF) and `error` (e.g., #FF0000) in the active theme and applies them.

## How to Use `ThemedBox`

`ThemedBox` wraps Ink's `<Box>` component. It is primarily used for layout, borders, and background colors.

### The Border Trick
In standard Ink, you set a border color with a hex code. In `ThemedBox`, we intercept that property.

```tsx
import { ThemedBox } from './design-system';

<ThemedBox 
  borderColor="warning" 
  borderStyle="single" 
  padding={1}
>
  {/* Children go here */}
</ThemedBox>
```

**Note:** Props that *aren't* related to color (like `padding`, `margin`, `flexDirection`) are passed directly through to the underlying Ink Box.

## How It Works Under the Hood

Let's visualize the conversation between your component and the system when you try to render a "Success" box.

```mermaid
sequenceDiagram
    participant App as Your App
    participant Box as ThemedBox
    participant Theme as ThemeProvider
    participant Ink as Raw Ink Box

    App->>Box: Render with borderColor="success"
    
    Box->>Theme: "Get current theme palette"
    Theme-->>Box: Returns { success: "#00FF00", ... }
    
    Box->>Box: Translate "success" -> "#00FF00"
    
    Box->>Ink: Render with borderColor="#00FF00"
    Ink-->>App: Displays Green Border
```

1.  **Your App** asks for a semantic name (`success`).
2.  **ThemedBox** connects to the [Theming Context](01_theming_context___utilities.md) to get the dictionary of colors.
3.  **ThemedBox** translates the name to a hex code.
4.  It passes the *real* hex code to the **Raw Ink Box**, which doesn't know about themes—it just draws colors.

## Internal Implementation Deep Dive

Let's look at the code inside `design-system` to see how we built these wrappers.

### 1. The Helper: `resolveColor`
Both Text and Box use a helper function to decide what to do.

```tsx
// Inside ThemedText.tsx / ThemedBox.tsx

function resolveColor(colorValue, theme) {
  if (!colorValue) return undefined;

  // 1. If it looks like a hex code (#fff), use it directly.
  if (colorValue.startsWith('#')) return colorValue;

  // 2. Otherwise, assume it's a key (like 'success') and look it up.
  return theme[colorValue];
}
```
*Explanation:* This allows us to still use raw hex codes if we absolutely have to, but defaults to looking up semantic keys.

### 2. The `ThemedText` Component
Here is the simplified logic for the Text wrapper.

```tsx
// ThemedText.tsx (Simplified)
export default function ThemedText({ color, children, ...props }) {
  // 1. Hook into the brain
  const [themeName] = useTheme();
  const theme = getTheme(themeName);

  // 2. Translate the color key
  const finalColor = resolveColor(color, theme);

  // 3. Render the raw Ink Text with the calculated color
  return <Text color={finalColor} {...props}>{children}</Text>;
}
```
*Beginner Note:* Notice how `...props` is used. This takes any other settings (like `bold` or `italic`) and passes them down blindly.

### 3. The `ThemedBox` Component
The Box component is slightly more complex because it has many color properties (border top, bottom, background, etc.).

```tsx
// ThemedBox.tsx (Simplified)
export default function ThemedBox({ borderColor, children, ...rest }) {
  const [themeName] = useTheme();
  const theme = getTheme(themeName);

  // Translate the border color
  const resolvedBorder = resolveColor(borderColor, theme);

  return (
    <Box borderColor={resolvedBorder} {...rest}>
      {children}
    </Box>
  );
}
```
*Explanation:* We intercept `borderColor`, resolve it using the theme, and then pass the result to the real `Box`.

## Conclusion

By using **Theme-Aware Primitives**, we have separated *Business Logic* ("This is a success message") from *Design Details* ("Success messages are green").

*   **ThemedText** handles text coloring.
*   **ThemedBox** handles borders and backgrounds.

Now that we can color our atoms, we need to arrange them into useful shapes. In the next chapter, we will look at **Structural Containers**—pre-made layouts that help us organize information on the screen.

[Next Chapter: Structural Containers](03_structural_containers.md)

---

Generated by [Code IQ](https://github.com/adityasoni99/Code-IQ)