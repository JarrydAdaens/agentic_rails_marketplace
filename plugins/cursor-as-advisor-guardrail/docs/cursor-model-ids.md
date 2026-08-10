# Cursor model IDs

Every model ID the Cursor Agent CLI exposes, so an agent can turn a loose human
phrase — "that latest Grok one", "Opus with max thinking" — into the exact
string that goes into `harness/cursor-as-advisor-guardrail/config.json` or the
`model` argument of `consult_advisor`.

Captured from `agent models` on 10 August 2026. **Availability is account- and
version-dependent**: always confirm the chosen ID appears in that machine's own
`agent models` output before using it. If the two disagree, `agent models` wins.

## How to read an ID

An ID is a family plus suffixes. Nothing is configurable separately — the
suffixes *are* the configuration.

| Suffix | Meaning |
| --- | --- |
| `-none`, `-low`, `-medium`, `-high`, `-xhigh` / `-extra-high`, `-max` | Reasoning effort, ascending |
| `-thinking` | Extended-thinking variant of a Claude model (separate ladder from the non-thinking one) |
| `-fast` | Priority-speed variant. **Not** a different model — same model, faster serving |
| no effort suffix | Family has a single fixed level (e.g. `gpt-5.2`, `gemini-3.1-pro`) |

The bracket override syntax that `agent models` advertises in its closing tip
(`--model 'claude-opus-4-8[context=1m,effort=high,fast=false]'`) is **rejected**
by the plugin's call path. Always use a plain ID from the tables below.

Display names are not a reliable guide — Cursor labels `claude-opus-5-high` as
"Opus 5 1M" and `claude-opus-4-7-xhigh` as "Opus 4.7 1M", dropping the effort
word. Trust the ID suffix, not the label.

## Resolving a human phrase to an ID

Rules to apply in order when a human names a model informally:

1. **Match the family** they named (Grok, Opus, Sonnet, Codex, Gemini…).
2. **"Latest" means the highest version number** in that family, not the
   longest ID.
3. **No effort stated → pick `-high`.** It is the standard working level; a
   family without `-high` gets its highest non-`max` level.
4. **Never pick a `-fast` ID unless the human said "fast"**, "quick", or
   "priority". Standard speed is the default.
5. **"Thinking" only when they say so** — for Claude families the thinking and
   non-thinking ladders are separate IDs.
6. **Verify against `agent models`** before writing the ID anywhere.

Worked examples:

| Human says | Correct ID |
| --- | --- |
| "that latest Grok one" | `cursor-grok-4.5-high` |
| "Grok, but quick" | `cursor-grok-4.5-high-fast` |
| "cheap Grok for smoke tests" | `cursor-grok-4.5-low` |
| "latest Opus" | `claude-opus-5-high` |
| "Opus with max thinking" | `claude-opus-5-thinking-max` |
| "Opus 4.8, extra high" | `claude-opus-4-8-xhigh` |
| "the Codex model" | `gpt-5.3-codex-high` |
| "GPT-5.6, the Sol one, max" | `gpt-5.6-sol-max` |
| "latest Sonnet, thinking" | `claude-sonnet-5-thinking-high` |
| "Gemini Flash" | `gemini-3.6-flash-high` |
| "Cursor's own model" | `composer-2.5` |
| "just let it pick" | `auto` |

## Grok — xAI via Cursor

| ID | Display name |
| --- | --- |
| `cursor-grok-4.5-low` | Cursor Grok 4.5 Low |
| `cursor-grok-4.5-low-fast` | Cursor Grok 4.5 Low Fast |
| `cursor-grok-4.5-medium` | Cursor Grok 4.5 Medium |
| `cursor-grok-4.5-medium-fast` | Cursor Grok 4.5 Medium Fast |
| **`cursor-grok-4.5-high`** | **Cursor Grok 4.5** — the plugin's default advisor |
| `cursor-grok-4.5-high-fast` | Cursor Grok 4.5 Fast |

Note there is no bare `cursor-grok-4.5` and no `grok-4.5-high`. The alias
`grok-4.5` is *accepted* by Cursor without error, but what it maps to is
undocumented — do not use it.

## Cursor Composer

| ID | Display name |
| --- | --- |
| `composer-2.5` | Composer 2.5 |
| `composer-2.5-fast` | Composer 2.5 Fast |

## Auto

| ID | Display name |
| --- | --- |
| `auto` | Auto (default) — Cursor chooses per request |

## Anthropic — Opus

Opus 5 (latest):

| ID | Display name |
| --- | --- |
| `claude-opus-5-low` / `claude-opus-5-low-fast` | Opus 5 1M Low |
| `claude-opus-5-medium` / `claude-opus-5-medium-fast` | Opus 5 1M Medium |
| `claude-opus-5-high` / `claude-opus-5-high-fast` | Opus 5 1M |
| `claude-opus-5-thinking-low` / `-low-fast` | Opus 5 1M Low Thinking |
| `claude-opus-5-thinking-medium` / `-medium-fast` | Opus 5 1M Medium Thinking |
| `claude-opus-5-thinking-high` / `-high-fast` | Opus 5 1M Thinking |
| `claude-opus-5-thinking-xhigh` / `-xhigh-fast` | Opus 5 1M Extra High Thinking |
| `claude-opus-5-thinking-max` / `-max-fast` | Opus 5 1M Max Thinking |

Opus 4.8:

| ID | Display name |
| --- | --- |
| `claude-opus-4-8-low` / `-low-fast` | Opus 4.8 1M Low |
| `claude-opus-4-8-medium` / `-medium-fast` | Opus 4.8 1M Medium |
| `claude-opus-4-8-high` / `-high-fast` | Opus 4.8 1M |
| `claude-opus-4-8-xhigh` / `-xhigh-fast` | Opus 4.8 1M Extra High |
| `claude-opus-4-8-max` / `-max-fast` | Opus 4.8 1M Max |
| `claude-opus-4-8-thinking-low` / `-low-fast` | Opus 4.8 1M Low Thinking |
| `claude-opus-4-8-thinking-medium` / `-medium-fast` | Opus 4.8 1M Medium Thinking |
| `claude-opus-4-8-thinking-high` / `-high-fast` | Opus 4.8 1M Thinking |
| `claude-opus-4-8-thinking-xhigh` / `-xhigh-fast` | Opus 4.8 1M Extra High Thinking |
| `claude-opus-4-8-thinking-max` / `-max-fast` | Opus 4.8 1M Max Thinking |

Opus 4.7:

| ID | Display name |
| --- | --- |
| `claude-opus-4-7-low` / `-low-fast` | Opus 4.7 1M Low |
| `claude-opus-4-7-medium` / `-medium-fast` | Opus 4.7 1M Medium |
| `claude-opus-4-7-high` / `-high-fast` | Opus 4.7 1M High |
| `claude-opus-4-7-xhigh` / `-xhigh-fast` | Opus 4.7 1M |
| `claude-opus-4-7-max` / `-max-fast` | Opus 4.7 1M Max |
| `claude-opus-4-7-thinking-low` / `-low-fast` | Opus 4.7 1M Low Thinking |
| `claude-opus-4-7-thinking-medium` / `-medium-fast` | Opus 4.7 1M Medium Thinking |
| `claude-opus-4-7-thinking-high` / `-high-fast` | Opus 4.7 1M High Thinking |
| `claude-opus-4-7-thinking-xhigh` / `-xhigh-fast` | Opus 4.7 1M Thinking |
| `claude-opus-4-7-thinking-max` / `-max-fast` | Opus 4.7 1M Max Thinking |

Older Opus — note the reversed word order (`4.6-opus`, not `opus-4-6`):

| ID | Display name |
| --- | --- |
| `claude-4.6-opus-high` | Opus 4.6 1M |
| `claude-4.6-opus-max` | Opus 4.6 1M Max |
| `claude-4.6-opus-high-thinking` | Opus 4.6 1M Thinking |
| `claude-4.6-opus-max-thinking` | Opus 4.6 1M Max Thinking |
| `claude-4.5-opus-high` | Opus 4.5 |
| `claude-4.5-opus-high-thinking` | Opus 4.5 Thinking |

## Anthropic — Sonnet

| ID | Display name |
| --- | --- |
| `claude-sonnet-5-low` | Sonnet 5 1M Low |
| `claude-sonnet-5-medium` | Sonnet 5 1M Medium |
| `claude-sonnet-5-high` | Sonnet 5 1M |
| `claude-sonnet-5-xhigh` | Sonnet 5 1M Extra High |
| `claude-sonnet-5-max` | Sonnet 5 1M Max |
| `claude-sonnet-5-thinking-low` | Sonnet 5 1M Low Thinking |
| `claude-sonnet-5-thinking-medium` | Sonnet 5 1M Medium Thinking |
| `claude-sonnet-5-thinking-high` | Sonnet 5 1M Thinking |
| `claude-sonnet-5-thinking-xhigh` | Sonnet 5 1M Extra High Thinking |
| `claude-sonnet-5-thinking-max` | Sonnet 5 1M Max Thinking |
| `claude-4.6-sonnet-medium` | Sonnet 4.6 1M |
| `claude-4.6-sonnet-medium-thinking` | Sonnet 4.6 1M Thinking |
| `claude-4.5-sonnet` | Sonnet 4.5 |
| `claude-4.5-sonnet-thinking` | Sonnet 4.5 Thinking |
| `claude-4-sonnet` | Sonnet 4 |
| `claude-4-sonnet-thinking` | Sonnet 4 Thinking |

## Anthropic — Fable 5

Every Fable ID is labeled **(NO ZDR)** in Cursor's listing — no zero data
retention. Do not select one for a repository with confidentiality
requirements without a deliberate decision.

| ID | Display name |
| --- | --- |
| `claude-fable-5-low` | Fable 5 1M Low (NO ZDR) |
| `claude-fable-5-medium` | Fable 5 1M Medium (NO ZDR) |
| `claude-fable-5-high` | Fable 5 1M (NO ZDR) |
| `claude-fable-5-xhigh` | Fable 5 1M Extra High (NO ZDR) |
| `claude-fable-5-max` | Fable 5 1M Max (NO ZDR) |
| `claude-fable-5-thinking-low` | Fable 5 1M Low Thinking (NO ZDR) |
| `claude-fable-5-thinking-medium` | Fable 5 1M Medium Thinking (NO ZDR) |
| `claude-fable-5-thinking-high` | Fable 5 1M Thinking (NO ZDR) |
| `claude-fable-5-thinking-xhigh` | Fable 5 1M Extra High Thinking (NO ZDR) |
| `claude-fable-5-thinking-max` | Fable 5 1M Max Thinking (NO ZDR) |

## OpenAI — Codex

| ID | Display name |
| --- | --- |
| `gpt-5.3-codex-low` / `-low-fast` | Codex 5.3 Low |
| `gpt-5.3-codex` / `gpt-5.3-codex-fast` | Codex 5.3 |
| `gpt-5.3-codex-high` / `-high-fast` | Codex 5.3 High |
| `gpt-5.3-codex-xhigh` / `-xhigh-fast` | Codex 5.3 Extra High |

## OpenAI — GPT-5.6 (Sol, Terra, Luna)

Three sibling lines with identical effort ladders. Each level has a `-fast`
twin; only the standard IDs are listed, append `-fast` for priority speed.

| Effort | Sol | Terra | Luna |
| --- | --- | --- | --- |
| None | `gpt-5.6-sol-none` | `gpt-5.6-terra-none` | `gpt-5.6-luna-none` |
| Low | `gpt-5.6-sol-low` | `gpt-5.6-terra-low` | `gpt-5.6-luna-low` |
| Medium | `gpt-5.6-sol-medium` | `gpt-5.6-terra-medium` | `gpt-5.6-luna-medium` |
| High | `gpt-5.6-sol-high` | `gpt-5.6-terra-high` | `gpt-5.6-luna-high` |
| Extra high | `gpt-5.6-sol-xhigh` | `gpt-5.6-terra-xhigh` | `gpt-5.6-luna-xhigh` |
| Max | `gpt-5.6-sol-max` | `gpt-5.6-terra-max` | `gpt-5.6-luna-max` |

## OpenAI — GPT-5.5 and earlier

| ID | Display name |
| --- | --- |
| `gpt-5.5-none` / `-none-fast` | GPT-5.5 1M None |
| `gpt-5.5-low` / `-low-fast` | GPT-5.5 1M Low |
| `gpt-5.5-medium` / `-medium-fast` | GPT-5.5 1M |
| `gpt-5.5-high` / `-high-fast` | GPT-5.5 1M High |
| `gpt-5.5-extra-high` / `-extra-high-fast` | GPT-5.5 1M Extra High — note `extra-high`, not `xhigh` |
| `gpt-5.4-low` | GPT-5.4 1M Low |
| `gpt-5.4-medium` / `-medium-fast` | GPT-5.4 1M |
| `gpt-5.4-high` / `-high-fast` | GPT-5.4 1M High |
| `gpt-5.4-xhigh` / `-xhigh-fast` | GPT-5.4 1M Extra High |
| `gpt-5.4-mini-none`, `-low`, `-medium`, `-high`, `-xhigh` | GPT-5.4 Mini ladder |
| `gpt-5.4-nano-none`, `-low`, `-medium`, `-high`, `-xhigh` | GPT-5.4 Nano ladder |
| `gpt-5.2` / `gpt-5.2-fast` | GPT-5.2 |
| `gpt-5.2-low` / `-low-fast` | GPT-5.2 Low |
| `gpt-5.2-high` / `-high-fast` | GPT-5.2 High |
| `gpt-5.2-xhigh` / `-xhigh-fast` | GPT-5.2 Extra High |
| `gpt-5.1-low`, `gpt-5.1`, `gpt-5.1-high` | GPT-5.1 ladder |
| `gpt-5-mini` | GPT-5 Mini |

## Google — Gemini

| ID | Display name |
| --- | --- |
| `gemini-3.6-flash-minimal` | Gemini 3.6 Flash Minimal |
| `gemini-3.6-flash-low` | Gemini 3.6 Flash Low |
| `gemini-3.6-flash-medium` | Gemini 3.6 Flash Medium |
| `gemini-3.6-flash-high` | Gemini 3.6 Flash |
| `gemini-3.5-flash` | Gemini 3.5 Flash |
| `gemini-3-flash` | Gemini 3 Flash |
| `gemini-3.1-pro` | Gemini 3.1 Pro |

## Moonshot and Zhipu

| ID | Display name |
| --- | --- |
| `kimi-k3-low` | Kimi K3 Low |
| `kimi-k3-high` | Kimi K3 High |
| `kimi-k3-max` | Kimi K3 |
| `kimi-k2.7-code` | Kimi K2.7 Code |
| `glm-5.2-high` | GLM 5.2 |
| `glm-5.2-max` | GLM 5.2 Max |

## Refreshing this catalog

```powershell
agent models
```

The output is the authority. When it diverges from these tables — Cursor adds
and retires models often — update this document from the output rather than
working around it.
