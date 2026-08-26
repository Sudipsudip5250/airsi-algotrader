# Proposal queue

Each `*.json` file in this directory is a versioned `ExperimentProposal`. Proposals are hypotheses for offline testing or documentation improvement. They are not orders, recommendations, or permission to trade.

The researcher creates proposals here. The evaluator reads them and writes matching results under `experiments/evaluations/`. A human reviewer records approval or rejection under `experiments/decisions/`. No proposal is applied to `bot/config.paper.json` or `bot/config.live.json`.
