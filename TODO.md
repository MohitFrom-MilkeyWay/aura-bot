# AI Girlfriend Bot (AURA) - Development TODO

## Stages 1–9 ✅

### Monetization fix (Stars-only content) ✅
- [x] Gems ONLY for extra messages after free daily limit
- [x] Bundles unlock = Telegram Stars only
- [x] Blur→unblur = Stars only (or Premium free)
- [x] First user message = 1 free CLEAR photo
- [x] After that free users: no clear auto-media
- [x] Premium: unlimited msgs + free clear + auto media

## Current rules
| Action | Currency |
|--------|----------|
| Extra message (after free limit) | 1 gem |
| Daily bonus / invite rewards | gems (earned free) |
| Buy gem packs | Stars → gems |
| Bundle unlock | Stars only |
| Unblur photo | Stars only |
| Premium subscription | Stars only |
| Unlimited clear media | Premium |

## Next ideas
- Level-up gem rewards
- Leaderboard
- Voice (paid later)


### Multi-bot (1 process, N tokens) ✅
- BOT_TOKENS=t1,t2,... or BOT_TOKEN + BOT_TOKEN_2...
- Per-bot SQLite: data/aura_<hash>.db
- Shared media + LLM keys + ADMIN_IDS
