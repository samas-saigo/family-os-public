"""Virtual monotonic time for synthetic Gmail HTTP tests; never actually sleep."""


class FakeClock:
    def __init__(self, start=0.0):
        self.now = start
        self.delays = []

    def clock(self):
        return self.now

    def sleep(self, delay):
        assert delay > 0
        self.delays.append(delay)
        self.now += delay
