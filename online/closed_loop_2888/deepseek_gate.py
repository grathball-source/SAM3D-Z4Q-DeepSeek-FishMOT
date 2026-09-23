"""DeepSeek decision contract; no fabricated Jev probabilities."""


def gate(votes, compiled):
    if not isinstance(votes, list) or len(votes) != 3:
        return None, "invalid_vote_batch"
    keys = {"choice", "support_all", "displaced_all"}
    if any(not isinstance(v, dict) or set(v) != keys or
           not isinstance(v["choice"], str) or
           type(v["support_all"]) is not bool or
           type(v["displaced_all"]) is not bool for v in votes):
        return None, "invalid_vote_contract"
    choices = {v["choice"] for v in votes}
    if len(choices) != 1:
        return None, "vote_disagreement"
    choice = next(iter(choices))
    if choice in {"H0", "DEFER"}:
        return None, choice
    options = {f"P{i:02d}": p for i, p in enumerate(compiled["proposals"], 1)}
    proposal = options.get(choice)
    if proposal is None:
        return None, "unknown_proposal"
    if not all(v["support_all"] and (not proposal["displaced"] or v["displaced_all"]) for v in votes):
        return None, "whole_edit_not_unanimously_supported"
    return proposal, "qualifying_observation"
