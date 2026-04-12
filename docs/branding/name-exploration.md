# Name Exploration

## Purpose

The current repository name, `mobile-agent-runtime`, is descriptive but weak as a market-facing product name.

We want a name that can stand beside tools like Maestro, Appium, and RocketSim without sounding like internal plumbing.

## Naming criteria

A strong candidate should:
- be short and easy to say
- feel like a product, not only a codebase
- fit deterministic execution plus agent-native workflows
- still sound credible to serious mobile/platform engineers
- leave room for CLI, CI, and potential future product surfaces

## Candidate directions

### Lighthouse
Pros:
- strong metaphor for guidance, visibility, and reliable navigation
- very good fit for exploration, debugging, and agent workflows
- Daniel explicitly likes it

Cons:
- extremely crowded
- heavily associated with Google's web-performance tool
- likely difficult to own cleanly in developer-tooling contexts

External signal:
- GitHub search is very crowded; top results include GoogleChrome/lighthouse and other major projects

### Cadence
Pros:
- implies repeatability and controlled execution
- strong fit for CI and deterministic workflows
- serious technical tone

Cons:
- not obviously mobile
- existing developer-tooling usage already present

External signal:
- notable existing usage including cadence-workflow/cadence and onflow/cadence

### Beacon
Pros:
- good for exploration, guidance, and agent workflows
- recognizable and brandable

Cons:
- less obviously about execution/runtime
- crowded name family

External signal:
- crowded on GitHub; many existing Beacon projects

### Helix
Pros:
- stronger technical identity
- distinctive sound relative to generic runtime names

Cons:
- more abstract; less immediate product meaning
- significant existing software usage

External signal:
- notable collisions include helix-editor/helix and apache/helix

### Glide
Pros:
- subtle mobile/touch feel
- lightweight and product-like

Cons:
- may sound more consumer than infrastructure-grade
- already strongly occupied in developer tooling/mobile libraries

External signal:
- strong existing association with bumptech/glide

### Wayfinder
Pros:
- strong navigation/guidance metaphor similar to Lighthouse
- clearer product feel than an internal runtime label
- broad enough for execution + agent flows

Cons:
- slightly longer than Lighthouse/Cadence
- still somewhat abstract

External signal:
- much less crowded than Lighthouse/Beacon/Relay/Pilot on GitHub
- existing usage exists, but the collision surface appears materially lower

### SignalPath
Pros:
- evokes determinism, orchestration, and observable execution
- feels technical and infrastructure-credible
- relatively distinctive

Cons:
- more systems/infrastructure flavored than consumer-product flavored
- less elegant than Lighthouse

External signal:
- far less crowded than the more obvious one-word names in GitHub search

### Northstar
Pros:
- good metaphor for guidance and direction
- memorable and easy to say

Cons:
- somewhat common in product naming
- less directly tied to execution/runtime than some alternatives

External signal:
- moderate crowding, but cleaner than Lighthouse/Relay/Pilot/Orbit

## External signal snapshot

GitHub search is a useful early proxy for collision risk, even though it is not the whole branding picture.

Heavily crowded candidates:
- Lighthouse
- Relay
- Orbit
- Pilot
- Beacon
- Glide
- Helix
- Cadence

Cleaner candidates from the second pass:
- Wayfinder
- SignalPath
- Northstar
- GuideLight (cleaner, but weaker as a product name)

## Current recommendation

Best current balance of product feel + distinctiveness:
- Lighthouse as the strongest emotional/product direction
- Wayfinder as a strong cleaner alternative
- SignalPath as a more technical/distinctive alternative
- Cadence as the strongest deterministic-execution name if we prioritize seriousness over uniqueness

## Next pass recommendation

The next pass should evaluate the top 3-5 candidates across:
- memorability
- seriousness/credibility
- distinctiveness in mobile/devtool markets
- GitHub/domain/package conflicts
- whether the name can grow beyond pure CLI positioning
- whether the name over-indexes on guidance vs execution

Tracked issue:
- #9
