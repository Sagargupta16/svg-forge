---
description: 'React and Motion cover scene for a card: read-through cache mechanism.'
tags: [motion-scene, scaffold]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

Our project cards in `src/components/ProjectCard.tsx` have an empty media slot. Build an animated cover scene for the card of our caching service that shows how a read-through cache works: the first read misses, goes to the database and fills the cache, and the next read is a hit. Put the component in `src/scenes/CacheScene.tsx`. The app is React 19 with motion installed.
