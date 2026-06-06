# Auth Implementation – Changes

## Overview

Full authentication system added to FinMate-FE using React Context + AsyncStorage as the outermost provider. On app launch the token is read from persistent storage; users are routed automatically to the correct area and all protected routes are guarded from unauthenticated access.

---

## Files Changed / Created

### 1. `package.json` – new dependency
```
@react-native-async-storage/async-storage
```
Standard, battle-tested async key-value storage for React Native. Used to persist the auth token across app restarts.

---

### 2. `src/context/AuthContext.tsx` *(new file)*

**Purpose:** Single source of truth for authentication state across the entire app.

**What it does:**
- Exports `AuthProvider` – wraps the whole app and bootstraps auth on mount.
- On mount, reads `@finmate_auth_token` from AsyncStorage.
  - If a token is found → user is considered authenticated (`token !== null`).
  - If nothing is found or an error occurs → `token` stays `null`.
- Sets `isLoading = true` until the AsyncStorage read completes, then `false`. This prevents premature navigation before we know the auth state.
- Exports `useAuth()` hook that exposes:
  | Property | Type | Description |
  |---|---|---|
  | `token` | `string \| null` | Current auth token, `null` if unauthenticated |
  | `isLoading` | `boolean` | `true` while reading from AsyncStorage |
  | `login(token)` | `async fn` | Saves token to AsyncStorage and sets state |
  | `logout()` | `async fn` | Removes token from AsyncStorage and clears state |

---

### 3. `src/services/auth.ts` – replaced mock with real API

**Before:** Hardcoded credentials check with artificial delay; returned a mock token string.

**After:** Calls the real backend endpoint:
```
POST http://localhost:3100/api/v1/login/
Content-Type: application/json

{ "email": "", "password": "" }
```
- On success: parses `response.token` and returns it.
- On failure (`!response.ok`): extracts `message`, `detail`, or `error` from the JSON body and throws an `Error` so the login screen can display it.
- `LoginInput` type updated: field renamed from `identifier` → `email` to match the API contract.
- `signUpUser` remains mock (no signup endpoint specified yet) but returns a `token` field so it integrates with the same `login()` flow.

---

### 4. `src/app/_layout.tsx` – AuthProvider + AuthGuard

This is the **outermost** change. The root layout now:

1. Loads fonts (unchanged).
2. Wraps everything inside `<AuthProvider>` so auth state is available to every screen.
3. Renders `<AuthGuard />` as a sibling of the `<Stack>` navigator.

#### `AuthGuard` component

A non-rendering component (`return null`) that watches three values via `useEffect`:
- `token` – current auth token
- `isLoading` – whether AsyncStorage bootstrap is still running
- `segments` – current route segments from Expo Router's `useSegments()`

**Navigation rules applied on every change:**

| Condition | Action |
|---|---|
| `isLoading === true` | Do nothing – wait for bootstrap |
| `token === null` AND route is `(tabs)` or `dashboard` | `router.replace("/")` → send to Login |
| `token !== null` AND route is `/`, `/signup`, or `/signup-flow` | `router.replace("/(tabs)")` → send to Dashboard tabs |
| Anything else | No navigation – stay where you are |

**Route classification:**

```
Public  (no token needed):  /  (login)  /signup  /signup-flow
Protected (token required):  /(tabs)/*   /dashboard
```

---

### 5. `src/app/index.tsx` – Login screen wired to real auth

Changes:
- Imports `useAuth` and calls `login(token)` after a successful API response.
- State variable renamed: `identifier` → `email`.
- `TextInput` now sets `keyboardType="email-address"` for better UX.
- Removed `router.replace("/dashboard")` – navigation is handled entirely by `AuthGuard` reacting to the token state change. This avoids double-navigation and keeps one source of truth.

---

### 6. `src/app/signup-flow.tsx` – Signup flow wired to auth

Changes:
- Imports `useAuth` and calls `login(token)` after `signUpUser` resolves successfully.
- Removed `router.replace("/dashboard")` – same reason as above; `AuthGuard` reacts to the token and navigates to `/(tabs)`.

---

## App Boot Flow (full sequence)

```
App launches
  │
  ├─ RootLayout renders
  │    ├─ Loads fonts (SplashScreen stays up)
  │    └─ Renders <AuthProvider>
  │         │
  │         ├─ bootstrap() fires
  │         │    └─ AsyncStorage.getItem("@finmate_auth_token")
  │         │         ├─ token found   → setToken(token), setIsLoading(false)
  │         │         └─ no token/err  → setToken(null),  setIsLoading(false)
  │         │
  │         └─ Renders <RootLayoutNav>
  │              ├─ <AuthGuard /> (watches token + segments)
  │              └─ <Stack>  (all screens registered)
  │
  ├─ Fonts loaded → SplashScreen.hideAsync()
  │
  └─ isLoading becomes false → AuthGuard evaluates current route
       ├─ token === null  →  force route to "/"  (Login screen)
       └─ token !== null  →  force route to "/(tabs)" (Dashboard)
```

---

## Login Flow

```
User on Login screen  (/index.tsx)
  │
  ├─ Fills email + password → taps "Login"
  ├─ loginUser({ email, password }) → POST /api/v1/login/
  │    ├─ 200 OK  →  { token: "..." }
  │    └─ Non-2xx → throws Error with server message → shown in UI
  │
  ├─ login(token)  ←  useAuth()
  │    └─ AsyncStorage.setItem + setToken(token)
  │
  └─ AuthGuard useEffect fires (token changed, segment is "/")
       └─ router.replace("/(tabs)")  →  User lands on Dashboard
```

---

## Logout Flow (when implemented on Profile screen)

```
User taps "Logout"
  │
  ├─ logout()  ←  useAuth()
  │    └─ AsyncStorage.removeItem + setToken(null)
  │
  └─ AuthGuard useEffect fires (token is null, segment is "(tabs)")
       └─ router.replace("/")  →  User lands on Login screen
```

To add a logout button on any screen:
```tsx
import { useAuth } from "@/context/AuthContext";

const { logout } = useAuth();
// ...
<Button onPress={logout} title="Log Out" />
```

---

## Protected vs Public Route Summary

| Route | Public | Protected |
|---|:---:|:---:|
| `/` (Login) | ✓ | – |
| `/signup` | ✓ | – |
| `/signup-flow` | ✓ | – |
| `/(tabs)/dashboard` | – | ✓ |
| `/(tabs)/portfolio` | – | ✓ |
| `/(tabs)/insights` | – | ✓ |
| `/(tabs)/wallet` | – | ✓ |
| `/(tabs)/profile` | – | ✓ |
| `/dashboard` (legacy) | – | ✓ |
