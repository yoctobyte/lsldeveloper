class StateChangeException(Exception):
    def __init__(self, new_state: str):
        self.new_state = new_state
