from server.workflow.state import ReviewState


class RoundManager:
    def run(self, state: ReviewState) -> ReviewState:
        return self.increment_round(state)

    def increment_round(self, state: ReviewState) -> ReviewState:
        new_state = state.copy()
        new_state["current_round"] = state["current_round"] + 1
        return new_state
